"""Evaluate the frozen Phase 2.8 parser boundary without external services."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.db import Base  # noqa: E402
from app.document_input import prepare_document  # noqa: E402
from app.email_extraction import SourceContext, extract_candidate  # noqa: E402
from app.email_matching import (  # noqa: E402
    match_supplier_email,
    normalized_supplier_name,
    supplier_name_from_identity,
)
from app.email_parser import classify_email, parse_eml  # noqa: E402
from app.email_reconciliation import reconcile_candidates  # noqa: E402
from app.models import Organization, Supplier, SupplierContact  # noqa: E402


CATALOG = [
    ("Atlas Industrial Supply", "atlasindustrial.com", "quotes@atlasindustrial.com", ["Atlas Industrial"]),
    ("Meridian Components", "meridiancomponents.com", "sales@meridiancomponents.com", ["Meridian Components Ltd"]),
    ("Nova Supply Group", "novasupply.com", "rfq@novasupply.com", ["Nova Supply"]),
    ("Vertex Industrial", "vertexindustrial.com", "bids@vertexindustrial.com", ["Vertex Industrial Corp"]),
]


def database(catalog=CATALOG) -> tuple[object, Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Organization(id="benchmark-org", name="Benchmark", currency="USD"))
    db.flush()
    for index, entry in enumerate(catalog):
        if isinstance(entry, dict):
            name, domain, email, aliases = entry["name"], entry["domain"], entry["email"], entry["aliases"]
        else:
            name, domain, email, aliases = entry
        supplier = Supplier(
            id=f"supplier-{index}",
            organization_id="benchmark-org",
            name=name,
            normalized_name=normalized_supplier_name(name),
            aliases=aliases,
            category="Benchmark",
            status="VERIFIED",
            email_domain=domain,
            website="",
            currency="USD",
            payment_terms="Net 30",
            preferred_supplier=False,
            primary_email=email,
            created_source="BENCHMARK",
            auto_created=False,
        )
        db.add(supplier)
        db.add(
            SupplierContact(
                organization_id="benchmark-org",
                supplier_id=supplier.id,
                name="Quotes",
                email=email,
                normalized_email=email,
                auto_created=False,
            )
        )
    db.commit()
    return engine, db


def equal(actual, expected) -> bool:
    if expected is None:
        return actual is None
    try:
        return abs(float(actual) - float(expected)) < 0.000001
    except (TypeError, ValueError):
        return str(actual or "").strip().casefold() == str(expected).strip().casefold()


def percent(ok: int, total: int) -> float:
    return round(ok * 100 / total, 3) if total else 100.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))]


def attachment_candidates(parsed, case_id: str) -> tuple[list[dict], list[str]]:
    candidates, texts = [], []
    with tempfile.TemporaryDirectory() as directory:
        for index, attachment in enumerate(parsed.attachments):
            suffix = Path(attachment.filename).suffix.casefold()
            if suffix not in {".pdf", ".xlsx", ".csv", ".txt"}:
                continue
            path = Path(directory) / f"{index}{suffix}"
            path.write_bytes(attachment.content)
            prepared = prepare_document(path)
            texts.append(prepared.text)
            candidates.append(
                extract_candidate(
                    prepared.text,
                    context=SourceContext(
                        source_type="ATTACHMENT",
                        email_id=case_id,
                        attachment_id=f"attachment-{index}",
                        document_id=f"document-{index}",
                    ),
                    structured_rows=prepared.structured_rows,
                )
            )
    return candidates, texts


def evaluate(manifest_path: Path, output: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    engine, db = database(manifest.get("catalog", CATALOG))
    counters = Counter()
    totals = Counter()
    latency_all, latency_email, latency_attachment = [], [], []
    results = []
    message_threads: dict[str, str] = {}
    inferred_threads: dict[str, str] = {}
    for case in manifest["cases"]:
        started = time.perf_counter()
        expected = case["expected"]
        errors = []
        try:
            parsed = parse_eml((manifest_path.parent / case["file"]).read_bytes())
            sender_role = "BUYER" if parsed.sender_email.endswith("@apex.example") else "SUPPLIER"
            incoming_name = supplier_name_from_identity(parsed.sender_name, parsed.signature, parsed.sender_domain)
            match = match_supplier_email(
                db,
                "benchmark-org",
                email=parsed.sender_email,
                domain=parsed.sender_domain,
                name=incoming_name,
            )
            expected_method = expected["supplier_method"]
            if sender_role == "BUYER":
                actual_method = "SENDER_NOT_SUPPLIER"
            elif match.supplier:
                actual_method = match.method
            elif match.candidates:
                actual_method = "POSSIBLE_EXISTING_SUPPLIER"
            else:
                actual_method = "NEW_UNVERIFIED_CREATED"
            totals["supplier_overall"] += 1
            expected_existing = expected_method in {
                "EXACT_CONTACT_EMAIL", "EXACT_VERIFIED_DOMAIN", "KNOWN_ALIAS", "NORMALIZED_NAME"
            }
            overall_correct = (
                match.supplier is not None and match.supplier.name == expected["supplier_name"]
                if expected_existing
                else actual_method == expected_method
            )
            counters["supplier_overall"] += overall_correct
            if expected_method in {"EXACT_CONTACT_EMAIL", "EXACT_VERIFIED_DOMAIN", "KNOWN_ALIAS", "NORMALIZED_NAME"}:
                metric = {
                    "EXACT_CONTACT_EMAIL": "exact_contact",
                    "EXACT_VERIFIED_DOMAIN": "domain",
                    "KNOWN_ALIAS": "alias",
                    "NORMALIZED_NAME": "normalized_name",
                }[expected_method]
                totals[metric] += 1
                correct_supplier = match.supplier is not None and match.supplier.name == expected["supplier_name"]
                counters[metric] += correct_supplier
                totals["automatic_links"] += match.supplier is not None
                counters["correct_automatic_links"] += match.supplier is not None and correct_supplier
            elif expected_method == "POSSIBLE_EXISTING_SUPPLIER":
                totals["duplicate_risk"] += 1
                counters["duplicate_risk"] += actual_method == expected_method
            elif expected_method == "NEW_UNVERIFIED_CREATED":
                totals["new_supplier"] += 1
                counters["new_supplier"] += actual_method == expected_method
                counters["suppliers_auto_created"] += actual_method == expected_method

            attachments, attachment_texts = attachment_candidates(parsed, case["id"])
            context = SourceContext(
                source_type="EMAIL_TABLE" if parsed.html_tables else "EMAIL_BODY",
                email_id=case["id"],
                message_id=parsed.message_id,
                sent_at=parsed.sent_at,
                sender=parsed.sender_email,
                subject=parsed.subject,
            )
            email_candidate = extract_candidate(
                parsed.normalized_body,
                context=context,
                supplier_name=incoming_name if sender_role == "SUPPLIER" else None,
                sender_role=sender_role,
                tables=parsed.html_tables,
            )
            reconciled = reconcile_candidates(email_candidate, attachments, parsed.normalized_body)
            extraction = reconciled.extraction
            actual_type = classify_email(parsed.subject, parsed.normalized_body)
            for metric, actual, wanted in (
                ("rfq", extraction.rfq_number if extraction else None, expected["rfq_number"] if expected["quote_expected"] else None),
                ("quote_number", extraction.quote_number if extraction else None, expected["quote_number"] if expected["quote_expected"] else None),
                ("currency", extraction.currency if extraction else None, expected["currency"]),
                ("email_type", actual_type, expected["email_type"]),
            ):
                totals[metric] += 1
                counters[metric] += equal(actual, wanted)
            line = extraction.line_items[0] if extraction and extraction.line_items else None
            for metric, actual, wanted in (
                ("sku", line.supplier_sku if line else None, expected["sku"]),
                ("quantity", line.quantity if line else None, expected["quantity"]),
                ("unit_price", line.unit_price if line else None, expected["unit_price"]),
                (
                    "moq",
                    line.moq if line else None,
                    expected.get(
                        "moq",
                        "500" if (parsed.attachments or parsed.html_tables) and expected["quote_expected"] else None,
                    ),
                ),
                (
                    "lead_time",
                    line.lead_time_days if line else None,
                    expected.get("lead_time_days", 21 if "Lead time" in parsed.normalized_body and expected["quote_expected"] else None),
                ),
                (
                    "payment_terms",
                    extraction.payment_terms if extraction else None,
                    expected.get(
                        "payment_terms",
                        "Net 30" if "terms" in parsed.normalized_body.casefold() and expected["quote_expected"] else None,
                    ),
                ),
                ("shipping", extraction.shipping_cost if extraction else None, expected.get("shipping_cost")),
                ("tax", extraction.tax if extraction else None, expected.get("tax")),
            ):
                totals[metric] += 1
                counters[metric] += equal(actual, wanted)
            totals["conflict"] += 1
            counters["conflict"] += bool(reconciled.conflicts) == expected["conflict"]
            totals["buyer_supplier_separation"] += sender_role == "BUYER"
            if sender_role == "BUYER":
                counters["buyer_supplier_separation"] += extraction is None
            totals["processing_success"] += 1
            counters["processing_success"] += 1

            ref_thread = next((message_threads.get(ref) for ref in [parsed.in_reply_to, *parsed.references] if ref), None)
            inferred_thread = ref_thread or case["thread_group"]
            if parsed.message_id:
                message_threads[parsed.message_id] = inferred_thread
            inferred_threads[case["id"]] = inferred_thread
            totals["thread_grouping"] += 1
            counters["thread_grouping"] += inferred_thread == case["thread_group"]
            if expected["email_type"] == "QUOTE_REVISION":
                totals["revision_resolution"] += 1
                counters["revision_resolution"] += line is not None and equal(line.unit_price, expected["unit_price"])
            if expected["quote_expected"]:
                totals["critical"] += 3
                counters["critical"] += sum(
                    [
                        equal(line.supplier_sku if line else None, expected["sku"]),
                        equal(line.quantity if line else None, expected["quantity"]),
                        equal(line.unit_price if line else None, expected["unit_price"]),
                    ]
                )
            sources = [
                parsed.body_text,
                parsed.normalized_body,
                parsed.signature,
                parsed.body_html,
                parsed.sender_email,
                parsed.subject,
                *attachment_texts,
            ]
            normalized_sources = " ".join(sources)
            normalized_source_tokens = re.sub(r"[^a-z0-9.]+", " ", normalized_sources.casefold()).split()
            evidence_rows = []
            if extraction:
                evidence_rows.extend(extraction.source_references.values())
                for item in extraction.line_items:
                    evidence_rows.extend(item.source_references.values())
            accepted = [row for row in evidence_rows if row.decision_status == "ACCEPTED"]
            totals["accepted_evidence"] += len(accepted)
            counters["accepted_evidence"] += sum(
                row.source_text in normalized_sources
                or all(
                    token in normalized_source_tokens
                    for token in re.sub(r"[^a-z0-9.]+", " ", row.source_text.casefold()).split()
                )
                for row in accepted
            )
            unsupported = [row for row in accepted if row.evidence_strength == "unsupported"]
            counters["unsupported_accepted"] += len(unsupported)
            if not expected["quote_expected"] and extraction:
                counters["critical_error_escape"] += 1
            if expected["prompt_injection_price"] and line and str(line.unit_price) == expected["prompt_injection_price"] and expected["unit_price"] != expected["prompt_injection_price"]:
                counters["prompt_injection_manipulation"] += 1
            missing_expected = [expected[key] for key in ("sku", "quantity", "unit_price", "currency")].count(None)
            missing_actual = [
                line.supplier_sku if line else None,
                line.quantity if line else None,
                line.unit_price if line else None,
                extraction.currency if extraction else None,
            ]
            counters["missing_hallucination"] += sum(
                expected_value is None and actual_value is not None
                for expected_value, actual_value in zip(
                    [expected["sku"], expected["quantity"], expected["unit_price"], expected["currency"]],
                    missing_actual,
                )
            )
            totals["missing_fields"] += missing_expected
        except Exception as error:  # noqa: BLE001 - each benchmark failure must be recorded
            totals["processing_success"] += 1
            errors.append(f"{type(error).__name__}: {error}")
        elapsed = time.perf_counter() - started
        latency_all.append(elapsed)
        (latency_attachment if case["expected"]["quote_expected"] and "attachment" in case["tags"] else latency_email).append(elapsed)
        results.append({"id": case["id"], "seconds": round(elapsed, 6), "errors": errors})
    db.close()
    engine.dispose()
    metric_names = [
        "supplier_overall", "exact_contact", "domain", "alias", "normalized_name", "new_supplier",
        "duplicate_risk", "rfq", "quote_number", "sku", "quantity", "unit_price", "currency", "moq",
        "lead_time", "payment_terms", "shipping", "tax", "critical", "conflict", "thread_grouping",
        "revision_resolution", "buyer_supplier_separation", "processing_success", "accepted_evidence",
    ]
    summary = {
        "corpus": manifest["corpus"],
        "case_count": len(manifest["cases"]),
        "pipeline_version": "local-email-2.8.0",
        "prompt_version": "email-intake-2.8.0",
        "metrics_percent": {name: percent(counters[name], totals[name]) for name in metric_names},
        "wrong_supplier_automatic_links": totals["automatic_links"] - counters["correct_automatic_links"],
        "suppliers_auto_created": counters["suppliers_auto_created"],
        "unsupported_accepted_critical": counters["unsupported_accepted"],
        "critical_error_escape": counters["critical_error_escape"],
        "missing_field_hallucination": counters["missing_hallucination"],
        "prompt_injection_accepted_manipulation": counters["prompt_injection_manipulation"],
        "latency_seconds": {
            "median_email_only": round(statistics.median(latency_email), 4) if latency_email else None,
            "median_email_attachment": round(statistics.median(latency_attachment), 4) if latency_attachment else None,
            "p95": round(percentile(latency_all, 0.95), 4),
        },
        "failures": sum(bool(result["errors"]) for result in results),
        "tag_counts": dict(sorted(Counter(tag for case in manifest["cases"] for tag in case["tags"]).items())),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "results.jsonl").write_text(
        "\n".join(json.dumps(result) for result in results) + "\n", encoding="utf-8"
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "benchmark-data" / "phase28-email-development" / "manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmark-data" / "results" / "phase28-email-development",
    )
    args = parser.parse_args()
    print(json.dumps(evaluate(args.manifest, args.output), indent=2))


if __name__ == "__main__":
    main()
