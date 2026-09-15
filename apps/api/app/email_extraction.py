"""Deterministic procurement candidates from current email content and tables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .email_matching import rfq_token
from .structured_input import semantic_header


@dataclass(frozen=True)
class SourceContext:
    source_type: str
    email_id: str | None = None
    message_id: str | None = None
    sent_at: object | None = None
    sender: str | None = None
    subject: str | None = None
    attachment_id: str | None = None
    document_id: str | None = None


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", value.replace(",", ""))
    try:
        return Decimal(cleaned) if cleaned and cleaned not in {"-", "."} else None
    except InvalidOperation:
        return None


def _evidence(context: SourceContext, snippet: str, value, status="ACCEPTED", reason=None) -> dict:
    return {
        "document_id": context.document_id,
        "source_text": snippet[:4000],
        "confidence": "1" if status == "ACCEPTED" else "0.5",
        "evidence_type": "text",
        "evidence_strength": "strong" if status == "ACCEPTED" else "weak",
        "source_status": "PRESENT",
        "decision_status": status,
        "reason": reason,
        "raw_candidate": str(value) if value is not None else None,
        "accepted_value": str(value) if status == "ACCEPTED" and value is not None else None,
        "email_id": context.email_id,
        "message_id": context.message_id,
        "sent_at": context.sent_at,
        "sender": context.sender,
        "subject": context.subject,
        "source_type": context.source_type,
        "attachment_id": context.attachment_id,
    }


def _set(candidate: dict, key: str, value, snippet: str, context: SourceContext, status="ACCEPTED", reason=None):
    if value is None or value == "":
        return
    candidate[key] = value
    candidate.setdefault("source_references", {})[key] = _evidence(context, snippet, value, status, reason)


def _line_set(line: dict, key: str, value, snippet: str, context: SourceContext, status="ACCEPTED", reason=None):
    if value is None or value == "":
        return
    line[key] = value
    line.setdefault("source_references", {})[key] = _evidence(context, snippet, value, status, reason)


def _header_mapping(rows: list[list[str]], context: SourceContext) -> list[dict]:
    lines: list[dict] = []
    headers: list[str | None] | None = None
    for row in rows:
        semantic = [semantic_header(cell) for cell in row]
        if sum(value is not None for value in semantic) >= 2 and any(
            value in semantic for value in ("supplier_sku", "description")
        ):
            headers = semantic
            continue
        if not headers or not any(str(cell).strip() for cell in row):
            continue
        line = {"source_references": {}, "price_tiers": []}
        snippet = " | ".join(str(cell).strip() for cell in row)
        for index, key in enumerate(headers):
            if not key or index >= len(row):
                continue
            raw = str(row[index]).strip()
            if not raw:
                continue
            value = _decimal(raw) if key in {"quantity", "unit_price", "moq", "stated_line_total"} else raw
            if key == "lead_time_days":
                value = _lead_days(raw)
            _line_set(line, key, value, snippet, context)
        if any(line.get(key) is not None for key in ("supplier_sku", "description", "quantity", "unit_price")):
            lines.append(line)
    return lines


def _lead_days(value: str) -> int | None:
    numbers = [int(number) for number in re.findall(r"\d+", value)]
    if not numbers:
        return None
    return max(numbers) * (7 if re.search(r"week|wk", value, re.I) else 1)


def _structured_rows(rows: list[dict], context: SourceContext) -> list[dict]:
    result = []
    for row in rows:
        cells = row.get("field_cells") or {}
        if not cells:
            continue
        line = {"source_references": {}, "price_tiers": []}
        snippet = row.get("raw_text") or " | ".join(str(v.get("value") or "") for v in cells.values())
        for key, cell in cells.items():
            raw = cell.get("value")
            value = _decimal(str(raw)) if key in {"quantity", "unit_price", "moq", "stated_line_total"} else raw
            if key == "lead_time_days" and raw is not None:
                value = _lead_days(str(raw))
            _line_set(line, key, value, snippet, context)
            if key in line["source_references"]:
                evidence = line["source_references"][key]
                evidence.update(
                    sheet=row.get("sheet"), row=row.get("row"), table=row.get("table"), bounding_box=cell.get("bbox")
                )
                cell_ref = cell.get("cell")
                if cell_ref:
                    evidence["cell"] = cell_ref.split("!", 1)[-1]
        if any(line.get(key) is not None for key in ("supplier_sku", "description", "quantity", "unit_price")):
            result.append(line)
    return result


def extract_candidate(
    text: str,
    *,
    context: SourceContext,
    supplier_name: str | None = None,
    sender_role: str = "SUPPLIER",
    tables: list[list[list[str]]] | None = None,
    structured_rows: list[dict] | None = None,
) -> dict:
    candidate: dict = {"source_references": {}, "line_items": []}
    if not supplier_name:
        supplier_match = re.search(
            r"^(?:supplier|vendor|company)\s*[:=-]\s*([^\n]{2,200})$", text, re.I | re.M
        )
        if supplier_match:
            supplier_name = _clean(supplier_match.group(1))
    if supplier_name:
        _set(candidate, "supplier_name", supplier_name, supplier_name, context)
    if context.sender and "@" in context.sender:
        _set(candidate, "supplier_email", context.sender, context.sender, context)
    rfq = rfq_token(f"{context.subject or ''}\n{text}")
    if rfq:
        snippet = next((line for line in f"{context.subject or ''}\n{text}".splitlines() if rfq_token(line)), rfq)
        _set(candidate, "rfq_number", rfq, snippet, context)
    quote_match = re.search(
        r"\b(?:quote|quotation)\s*(?:number|no\.?|#|ref)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{2,40})",
        f"{context.subject or ''}\n{text}",
        re.I,
    )
    if quote_match and not quote_match.group(1).casefold().startswith(
        ("is", "for", "attached", "revised", "updated", "generated", "available", "only", "subject")
    ):
        _set(candidate, "quote_number", quote_match.group(1), quote_match.group(0), context)
    currency_match = re.search(r"\b(USD|EUR|GBP|CAD|AUD|JPY|CNY|CHF|MXN)\b", text, re.I)
    if currency_match:
        _set(candidate, "currency", currency_match.group(1).upper(), currency_match.group(0), context)
    payment = re.search(r"\b(?:payment\s+terms?|terms?)\s*[:=-]?\s*(Net\s*\d{1,3}|Due\s+on\s+receipt|Prepaid)\b", text, re.I)
    if payment:
        _set(candidate, "payment_terms", _clean(payment.group(1)), payment.group(0), context)
    shipping_policy = re.search(r"\b(freight\s+(?:is\s+)?included|shipping\s+(?:is\s+)?included|FOB\s+[^\n,;]+)", text, re.I)
    if shipping_policy:
        _set(candidate, "shipping_terms", _clean(shipping_policy.group(1)), shipping_policy.group(0), context)
    for key, label in (("shipping_cost", r"shipping|freight"), ("tax", r"tax"), ("stated_subtotal", r"subtotal"), ("stated_total", r"(?:grand\s+)?total")):
        match = re.search(rf"\b(?:{label})\s*[:=-]?\s*(?:USD\s*)?\$?([0-9][0-9,]*(?:\.\d+)?)\b", text, re.I)
        if match:
            _set(candidate, key, _decimal(match.group(1)), match.group(0), context)

    for table in tables or []:
        candidate["line_items"].extend(_header_mapping(table, context))
    candidate["line_items"].extend(_structured_rows(structured_rows or [], context))
    if not candidate["line_items"]:
        candidate["line_items"] = _text_lines(text, context, sender_role)
    candidate["line_items"] = _deduplicate_lines(candidate["line_items"])
    return candidate


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;-")


def _text_lines(text: str, context: SourceContext, sender_role: str) -> list[dict]:
    if sender_role == "BUYER":
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    results: list[dict] = []
    current: dict | None = None
    conditional = re.compile(r"\bif\s+you\s+(?:order|purchase)|\b(?:minimum|at least)\s+[0-9,]+", re.I)
    for index, raw in enumerate(lines):
        sku_match = re.search(r"(?:\bSKU\s*[:#-]?\s*)?\b([A-Z]{1,8}[-_][A-Z0-9][A-Z0-9._/-]{1,30})\b", raw)
        if sku_match and not rfq_token(raw):
            if current and any(current.get(key) is not None for key in ("quantity", "unit_price")):
                results.append(current)
            current = {"source_references": {}, "price_tiers": []}
            _line_set(current, "supplier_sku", sku_match.group(1), raw, context)
        quantity = re.search(r"\b(?:qty|quantity)\s*[:=-]?\s*([0-9][0-9,]*(?:\.\d+)?)\b", raw, re.I)
        price = re.search(r"\b(?:unit\s+price|price\s+(?:each|per\s+unit)|unit\s+cost)\s*[:=-]?\s*(?:USD\s*)?\$?([0-9][0-9,]*(?:\.\d{1,6})?)\b", raw, re.I)
        offered = re.search(r"\b(?:we\s+can\s+(?:do|offer)|our\s+(?:best|revised)\s+price\s+is)\s*(?:USD\s*)?\$?([0-9][0-9,]*(?:\.\d{1,6})?)", raw, re.I)
        moq = re.search(r"\bMOQ\s*[:=-]?\s*([0-9][0-9,]*(?:\.\d+)?)\b", raw, re.I)
        lead = re.search(r"\blead\s+time\s*[:=-]?\s*((?:\d+\s*(?:-|to)\s*)?\d+\s*(?:days?|weeks?|wks?))", raw, re.I)
        if any((quantity, price, offered, moq, lead)) and current is None:
            current = {"source_references": {}, "price_tiers": []}
        if current is None:
            continue
        if conditional.search(raw) and (price or offered):
            threshold = re.search(r"(?:order|purchase|minimum|at least)\s+([0-9][0-9,]*)", raw, re.I)
            amount = price.group(1) if price else offered.group(1)
            if threshold:
                current["price_tiers"].append(
                    {"minimum": str(_decimal(threshold.group(1))), "maximum": None, "unit_price": str(_decimal(amount))}
                )
            continue
        if quantity:
            _line_set(current, "quantity", _decimal(quantity.group(1)), raw, context)
        if price:
            _line_set(current, "unit_price", _decimal(price.group(1)), raw, context)
        elif offered:
            _line_set(current, "unit_price", _decimal(offered.group(1)), raw, context)
        if moq:
            _line_set(current, "moq", _decimal(moq.group(1)), raw, context)
        if lead:
            _line_set(current, "lead_time_days", _lead_days(lead.group(1)), raw, context)
        if index == len(lines) - 1 and current:
            results.append(current)
    if current and current not in results:
        results.append(current)
    return [
        line
        for line in results
        if any(line.get(key) is not None for key in ("supplier_sku", "quantity", "unit_price", "moq", "lead_time_days"))
    ]


def _deduplicate_lines(lines: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[tuple] = set()
    for line in lines:
        key = (
            str(line.get("supplier_sku") or "").casefold(),
            str(line.get("quantity") or ""),
            str(line.get("unit_price") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def candidate_has_quote(candidate: dict) -> bool:
    return bool(
        candidate.get("quote_number")
        or candidate.get("rfq_number")
        or any(line.get("unit_price") is not None for line in candidate.get("line_items", []))
    )
