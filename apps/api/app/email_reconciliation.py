"""Evidence-aware reconciliation for email body and supported attachments."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from .schemas import QuoteExtraction


TOP_FIELDS = (
    "supplier_name",
    "supplier_email",
    "quote_number",
    "rfq_number",
    "currency",
    "payment_terms",
    "shipping_terms",
    "shipping_cost",
    "tax",
    "stated_subtotal",
    "stated_total",
)
LINE_FIELDS = (
    "supplier_sku",
    "manufacturer_part_number",
    "description",
    "quantity",
    "uom",
    "unit_price",
    "moq",
    "lead_time_days",
    "lead_time_min",
    "delivery_date",
    "stated_line_total",
)


@dataclass
class Conflict:
    field: str
    email_value: object
    attachment_value: object
    attachment_id: str | None
    resolution: str
    reason: str


@dataclass
class ReconciliationResult:
    extraction: QuoteExtraction | None
    conflicts: list[Conflict]
    needs_review: bool
    sources_used: list[str]


def _same(left, right) -> bool:
    return str(left or "").strip().casefold() == str(right or "").strip().casefold()


def _review_evidence(evidence: dict, reason: str) -> dict:
    result = copy.deepcopy(evidence)
    result.update(
        confidence="0.5",
        evidence_strength="weak",
        decision_status="REVIEW_REQUIRED",
        reason=reason,
        accepted_value=None,
    )
    return result


def _attachment_id(candidate: dict, path: str) -> str | None:
    if path.startswith("line_items."):
        _, index, field = path.split(".", 2)
        return (candidate.get("line_items", [])[int(index)].get("source_references", {}).get(field) or {}).get(
            "attachment_id"
        )
    return (candidate.get("source_references", {}).get(path) or {}).get("attachment_id")


def _attachment_preferred(body_text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:use|refer to|see)\s+(?:the\s+)?(?:revised|updated|final|attached)|"
            r"\b(?:revised|updated|final)\s+(?:attached\s+)?(?:quote|quotation|pricing)|"
            r"\battached\s+(?:quote|quotation)\s+(?:supersedes|replaces)",
            body_text,
            re.I,
        )
    )


def _line_key(line: dict, index: int) -> str:
    return str(line.get("supplier_sku") or line.get("manufacturer_part_number") or f"__index_{index}").casefold()


def reconcile_candidates(email: dict, attachments: list[dict], body_text: str) -> ReconciliationResult:
    merged = copy.deepcopy(email)
    merged.setdefault("source_references", {})
    merged.setdefault("line_items", [])
    conflicts: list[Conflict] = []
    needs_review = False
    prefer_attachment = _attachment_preferred(body_text)
    sources_used = ["EMAIL_BODY"] if any(email.get(field) is not None for field in TOP_FIELDS) or email.get("line_items") else []

    lines = {_line_key(line, index): copy.deepcopy(line) for index, line in enumerate(merged["line_items"])}
    for attachment in attachments:
        if any(attachment.get(field) is not None for field in TOP_FIELDS) or attachment.get("line_items"):
            sources_used.append("ATTACHMENT")
        for field in TOP_FIELDS:
            incoming = attachment.get(field)
            current = merged.get(field)
            if incoming is None:
                continue
            evidence = attachment.get("source_references", {}).get(field, {})
            if current is None:
                merged[field] = incoming
                merged["source_references"][field] = evidence
            elif not _same(current, incoming) and field not in {"supplier_name", "supplier_email"}:
                attachment_id = evidence.get("attachment_id")
                if prefer_attachment:
                    merged[field] = incoming
                    merged["source_references"][field] = evidence
                    resolution = "ATTACHMENT_PREFERRED"
                    reason = "The latest message explicitly directs the buyer to the revised attachment."
                else:
                    needs_review = True
                    resolution = "REVIEW_REQUIRED"
                    reason = "Email body and attachment provide different explicit values."
                    merged["source_references"][field] = _review_evidence(
                        merged["source_references"].get(field, evidence), reason
                    )
                conflicts.append(Conflict(field, current, incoming, attachment_id, resolution, reason))

        attachment_lines = attachment.get("line_items", [])
        for index, incoming_line in enumerate(attachment_lines):
            key = _line_key(incoming_line, index)
            if key not in lines and len(lines) == 1 and len(attachment_lines) == 1:
                existing_key = next(iter(lines))
                if existing_key.startswith("__index_") and not key.startswith("__index_"):
                    lines[key] = lines.pop(existing_key)
                elif key.startswith("__index_"):
                    key = existing_key
            if key not in lines:
                lines[key] = copy.deepcopy(incoming_line)
                continue
            current_line = lines[key]
            current_line.setdefault("source_references", {})
            current_line.setdefault("price_tiers", [])
            for field in LINE_FIELDS:
                incoming = incoming_line.get(field)
                current = current_line.get(field)
                if incoming is None:
                    continue
                evidence = incoming_line.get("source_references", {}).get(field, {})
                if current is None:
                    current_line[field] = incoming
                    current_line["source_references"][field] = evidence
                elif not _same(current, incoming):
                    path = f"line_items.{key}.{field}"
                    attachment_id = evidence.get("attachment_id")
                    if prefer_attachment:
                        current_line[field] = incoming
                        current_line["source_references"][field] = evidence
                        resolution = "ATTACHMENT_PREFERRED"
                        reason = "The latest message explicitly directs the buyer to the revised attachment."
                    else:
                        needs_review = True
                        resolution = "REVIEW_REQUIRED"
                        reason = "Email body and attachment provide different explicit line-item values."
                        current_line["source_references"][field] = _review_evidence(
                            current_line["source_references"].get(field, evidence), reason
                        )
                    conflicts.append(Conflict(path, current, incoming, attachment_id, resolution, reason))
            if incoming_line.get("price_tiers"):
                current_line["price_tiers"] = incoming_line["price_tiers"]

    merged["line_items"] = list(lines.values())
    # A single explicit attachment currency may qualify a dollar-denominated email
    # line in the same message/quote context. Location is never used.
    if not merged.get("currency"):
        currencies = {candidate.get("currency") for candidate in attachments if candidate.get("currency")}
        if len(currencies) == 1:
            merged["currency"] = next(iter(currencies))
            source = next(c for c in attachments if c.get("currency") == merged["currency"])
            merged["source_references"]["currency"] = source["source_references"]["currency"]

    if not merged["line_items"]:
        return ReconciliationResult(None, conflicts, True, sources_used)
    for line in merged["line_items"]:
        line.setdefault("confidence", "0.5" if needs_review else "1")
        line.setdefault("source_references", {})
        line.setdefault("price_tiers", [])
    merged.setdefault("confidence", "0.5" if needs_review else "1")
    try:
        extraction = QuoteExtraction.model_validate(merged)
    except ValueError:
        return ReconciliationResult(None, conflicts, True, sources_used)
    return ReconciliationResult(extraction, conflicts, needs_review, sorted(set(sources_used)))
