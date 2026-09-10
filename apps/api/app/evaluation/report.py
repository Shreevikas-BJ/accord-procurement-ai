import csv
import json
import math
import statistics
from collections import Counter, defaultdict


def percentage(a, b):
    return round(100 * a / b, 3) if b else None


def report(rows, output):
    fields = defaultdict(Counter)
    for row in rows:
        for key, metrics in row["metrics"]["fields"].items():
            fields[key].update(metrics)
    errors = [e for row in rows for e in row["metrics"]["errors"]]
    taxonomy = Counter(e["error_type"] for e in errors)
    document_errors = Counter(row["error_type"] for row in rows if row.get("error_type"))
    review_findings = Counter(f["code"] for row in rows for f in row["metadata"].get("findings", []))
    times = {}
    for stage in ("parsing_seconds", "ocr_seconds", "model_seconds", "validation_seconds", "total_seconds"):
        values = sorted(row.get("metadata", {}).get(stage, 0) for row in rows)
        times[stage] = (
            {
                "median": round(statistics.median(values), 3),
                "mean": round(statistics.mean(values), 3),
                "p95": round(values[max(0, math.ceil(len(values) * 0.95) - 1)], 3),
            }
            if values
            else {}
        )
    summary = {
        "documents": len(rows),
        "model": rows[0]["metadata"].get("model") if rows else None,
        "prompt_version": rows[0]["metadata"].get("prompt_version") if rows else None,
        "pipeline_version": rows[0]["metadata"].get("pipeline_version") if rows else None,
        "formats": dict(Counter(r["format"] for r in rows)),
        "schema_validity": percentage(sum(r["success"] for r in rows), len(rows)),
        "document_critical_success": percentage(
            sum(r["success"] and r["metrics"]["critical_correct"] == r["metrics"]["critical_total"] for r in rows),
            len(rows),
        ),
        "critical_field_accuracy": percentage(
            sum(r["metrics"]["critical_correct"] for r in rows), sum(r["metrics"]["critical_total"] for r in rows)
        ),
        "line_association_accuracy": percentage(
            sum(r["metrics"]["association_correct"] for r in rows), sum(r["metrics"]["association_total"] for r in rows)
        ),
        "needs_review_rate": percentage(
            sum(not r["success"] or r["metadata"].get("needs_review", True) for r in rows), len(rows)
        ),
        "failure_rate": percentage(sum(not r["success"] for r in rows), len(rows)),
        "human_corrections_per_document": None,
        "human_corrections_note": "Evaluation-only extraction does not simulate buyer corrections; measured separately in the UI workflow.",
        "fields": {
            k: {
                **v,
                "accuracy": percentage(v["correct"], v["total"]),
                "exact_accuracy": percentage(v["exact"], v["total"]),
                "present_accuracy": percentage(v["present_correct"], v["present_total"]),
                "null_accuracy": percentage(v["null_correct"], v["null_total"]),
            }
            for k, v in fields.items()
        },
        "timings": times,
        "error_taxonomy": dict(taxonomy),
        "document_error_taxonomy": dict(document_errors),
        "review_finding_taxonomy": dict(review_findings),
        "by_origin": {
            origin: {
                "documents": len(group),
                "schema_validity": percentage(sum(r["success"] for r in group), len(group)),
                "critical_accuracy": percentage(
                    sum(r["metrics"]["critical_correct"] for r in group),
                    sum(r["metrics"]["critical_total"] for r in group),
                ),
            }
            for origin in sorted({r["origin"] for r in rows})
            for group in [[r for r in rows if r["origin"] == origin]]
        },
        "fixture_fallbacks": sum(bool(r["metadata"].get("fallback")) for r in rows),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "failures.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    with (output / "fields.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["field", "accuracy", "exact_accuracy", "present_accuracy", "null_accuracy", "correct", "total"],
        )
        writer.writeheader()
        writer.writerows(
            {"field": k, **{m: v[m] for m in writer.fieldnames if m != "field"}} for k, v in summary["fields"].items()
        )
    lines = [
        "# Accord local extraction benchmark",
        "",
        f"Model: `{summary['model']}` · Prompt: `{summary['prompt_version']}` · Pipeline: `{summary['pipeline_version']}`",
        "",
        f"Documents: {len(rows)}. Schema valid: {summary['schema_validity']}%. Critical fields: {summary['critical_field_accuracy']}%. Entire document critical success: {summary['document_critical_success']}%.",
        "",
        f"Needs review trigger: {summary['needs_review_rate']}%. All procurement decisions still require human approval. Fixture fallbacks: {summary['fixture_fallbacks']}.",
        "",
        "| Field | Normalized accuracy | Exact representation | Present values | Missing values |",
        "|---|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {k} | {v['accuracy']}% | {v['exact_accuracy']}% | {v['present_accuracy']}% | {v['null_accuracy']}% |"
        for k, v in summary["fields"].items()
    ]
    lines += [
        "",
        "Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.",
        "",
        "## Timing (seconds)",
        "",
        "| Stage | Median | P95 |",
        "|---|---:|---:|",
    ]
    lines += [f"| {k} | {v.get('median')} | {v.get('p95')} |" for k, v in times.items()]
    lines += [
        "",
        "## Failure taxonomy",
        "",
        *[f"- {k}: {v}" for k, v in taxonomy.most_common()],
        "",
        "Document-level failures (separate from field counts): " + json.dumps(dict(document_errors)),
        "",
        "Review finding counts: " + json.dumps(dict(review_findings)),
        "",
        "## Failure examples",
        "",
        "All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.",
        "",
    ]
    example_documents = set()
    examples = []
    for error in errors:
        if error["document_id"] not in example_documents:
            examples.append(error)
            example_documents.add(error["document_id"])
    lines += [
        f"- `{e['document_id']}` / `{e['field']}`: expected `{e['expected']}`, extracted `{e['extracted']}`. {e['error_type']}; page {e['source_page'] or 'unknown'}. {e['investigation']}"
        for e in examples[:30]
    ]
    lines += [
        "",
        "## Limits",
        "",
        "Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
