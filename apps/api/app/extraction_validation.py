"""Deterministic review signals; source amounts are never replaced by arithmetic."""

import re
import time
from decimal import Decimal

from .schemas import Evidence

UOM_ALIASES = {
    "EACH": "EA",
    "EA": "EA",
    "PCS": "EA",
    "PC": "EA",
    "PIECE": "EA",
    "PIECES": "EA",
    "KILOGRAM": "KG",
    "KG": "KG",
    "BOX": "BOX",
    "BOXES": "BOX",
}


def normalize_uom(value):
    return UOM_ALIASES.get(value.strip().upper(), value.strip().upper()) if value else None


def validate_extraction(quote, document):
    from .source_evidence import derive_references, supports

    started = time.monotonic()
    findings = []
    derive_references(quote, document)

    def flag(code, field, message):
        findings.append({"code": code, "field": field, "message": message})

    def evidence(value, fields, prefix):
        for key in fields:
            if getattr(value, key) is None:
                flag("MISSING_FIELD", prefix + key, "Source value is missing; buyer verification required.")
                continue
            ref = value.source_references.get(key)
            page_text = document.pages.get(ref.page, "") if ref and document.pages else document.text
            if (
                ref
                and ref.source_text
                and ref.source_text in page_text
                and supports(key, getattr(value, key), ref.source_text)
            ):
                ref.evidence_type = "ocr" if ref.page in document.image_pages else "text"
                ref.confidence = Decimal("0.8")
            elif ref and ref.page in document.image_pages:
                # Visual page evidence is not a verified quotation.
                ref.source_text = ""
                ref.evidence_type = "visual"
                ref.confidence = Decimal("0.5")
            else:
                value.source_references[key] = Evidence(source_text="", confidence=0, evidence_type="missing")
                flag(
                    "SOURCE_EVIDENCE_ERROR", prefix + key, "No verified source text or page image supports this field."
                )

    evidence(quote, ("supplier_name", "quote_number", "currency"), "")
    evidence(quote, [field for field in ("shipping_cost", "tax") if getattr(quote, field) is not None], "")
    for field in ("shipping_cost", "tax"):
        if getattr(quote, field) is None:
            flag("MISSING_COST", field, "Cost is not explicitly stated; the evaluated total remains unavailable.")
    derived = []
    seen = set()
    for index, line in enumerate(quote.line_items):
        prefix = f"line_items.{index}."
        evidence(line, ("supplier_sku", "quantity", "uom", "unit_price"), prefix)
        evidence(
            line,
            [field for field in ("moq", "lead_time_days", "delivery_date") if getattr(line, field) is not None],
            prefix,
        )
        line.uom = normalize_uom(line.uom)
        identity = (line.supplier_sku, line.quantity, line.uom, line.unit_price)
        if identity in seen:
            flag("DUPLICATE_LINE", prefix + "supplier_sku", "Repeated line retained; confirm it is intentional.")
        seen.add(identity)
        amount = line.quantity * line.unit_price if line.quantity is not None and line.unit_price is not None else None
        derived.append(amount)
        if (
            amount is not None
            and line.stated_line_total is not None
            and abs(amount - line.stated_line_total) > Decimal("0.02")
        ):
            flag(
                "LINE_TOTAL_MISMATCH",
                prefix + "stated_line_total",
                "Quantity times unit price differs from reported line total; check decimal placement or discounts.",
            )
        if line.unit_price == 0:
            flag("ZERO_PRICE", prefix + "unit_price", "Confirm the supplier explicitly offered a zero price.")
        if line.moq is None:
            flag("MISSING_MOQ", prefix + "moq", "Minimum order quantity is not stated.")
        if line.lead_time_days is None and line.delivery_date is None:
            flag("MISSING_DELIVERY", prefix + "lead_time_days", "Delivery commitment is not stated.")
        if line.delivery_date and quote.quote_date and line.delivery_date < quote.quote_date:
            flag("SUSPICIOUS_DATE", prefix + "delivery_date", "Delivery precedes the quote date.")
        if line.price_tiers and line.quantity is not None:
            tiers = [
                t
                for t in line.price_tiers
                if t.minimum <= line.quantity and (t.maximum is None or line.quantity <= t.maximum)
            ]
            if len(tiers) != 1 or line.unit_price != tiers[0].unit_price:
                flag(
                    "TIER_PRICE_REVIEW",
                    prefix + "unit_price",
                    "Quoted unit price does not identify one matching quantity tier.",
                )
        line.confidence = Decimal("0.45") if any(f["field"].startswith(prefix) for f in findings) else Decimal("0.9")
    subtotal = sum(derived, Decimal(0)) if all(a is not None for a in derived) else None
    if (
        subtotal is not None
        and quote.stated_subtotal is not None
        and abs(subtotal - quote.stated_subtotal) > Decimal("0.02")
    ):
        flag(
            "SUBTOTAL_MISMATCH",
            "stated_subtotal",
            "Derived lines differ from reported subtotal; inspect discounts and line association.",
        )
    total = (
        subtotal + quote.tax + quote.shipping_cost
        if subtotal is not None and quote.tax is not None and quote.shipping_cost is not None
        else None
    )
    if total is not None and quote.stated_total is not None and abs(total - quote.stated_total) > Decimal("0.02"):
        flag(
            "GRAND_TOTAL_MISMATCH",
            "stated_total",
            "Derived subtotal plus stated tax and shipping differs from grand total.",
        )
    if quote.expiration_date and quote.quote_date and quote.expiration_date < quote.quote_date:
        flag("SUSPICIOUS_DATE", "expiration_date", "Expiration precedes quote date.")
    if document.metadata.get("omitted_pages"):
        flag(
            "PAGES_OMITTED",
            "document",
            "Only selected pages were extracted. Check omitted pages for additional items or terms.",
        )
    if document.metadata.get("parser_quality") == "low":
        flag("OCR_QUALITY", "document", "Little readable text; verify against original page images.")
    if re.search(r"ignore (all|previous)|system prompt|approve (this|the) quote", document.text, re.I):
        flag(
            "UNTRUSTED_INSTRUCTION",
            "document",
            "Instruction-like source text detected; verify every extracted value against the source.",
        )
    critical_codes = {
        "MISSING_FIELD",
        "LINE_TOTAL_MISMATCH",
        "SUBTOTAL_MISMATCH",
        "GRAND_TOTAL_MISMATCH",
        "DUPLICATE_LINE",
        "OCR_QUALITY",
        "UNTRUSTED_INSTRUCTION",
    }
    band = (
        "LOW"
        if any(f["code"] in critical_codes for f in findings)
        else "MEDIUM"
        if findings or document.images
        else "HIGH"
    )
    quote.confidence = {"LOW": Decimal("0.4"), "MEDIUM": Decimal("0.7"), "HIGH": Decimal("0.9")}[band]
    return {
        "confidence_band": band,
        "needs_review": band != "HIGH",
        "human_approval_required": True,
        "findings": findings,
        "derived_subtotal": str(subtotal) if subtotal is not None else None,
        "derived_total": str(total) if total is not None else None,
        "validation_seconds": round(time.monotonic() - started, 4),
    }
