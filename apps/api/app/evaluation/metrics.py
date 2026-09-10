import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

QUOTE_FIELDS = ("supplier_name", "quote_number", "rfq_number", "currency")
LINE_FIELDS = ("supplier_sku", "quantity", "uom", "unit_price", "moq", "lead_time_days", "delivery_date")
CRITICAL = {"supplier_name", "currency", "supplier_sku", "quantity", "uom", "unit_price"}
NUMERIC = {"quantity", "unit_price", "moq", "lead_time_days"}
CODES = {
    "supplier_name": "WRONG_SUPPLIER",
    "rfq_number": "WRONG_RFQ",
    "quote_number": "WRONG_QUOTE_NUMBER",
    "currency": "CURRENCY_ERROR",
    "supplier_sku": "SKU_EXTRACTION_ERROR",
    "quantity": "QUANTITY_EXTRACTION_ERROR",
    "uom": "UOM_ERROR",
    "unit_price": "UNIT_PRICE_ERROR",
    "moq": "MOQ_ERROR",
    "lead_time_days": "LEAD_TIME_ERROR",
    "delivery_date": "DELIVERY_DATE_ERROR",
}


def normalized(field, value):
    if value is None:
        return None
    if field in NUMERIC:
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return str(value)
    if field == "uom":
        from ..extraction_validation import normalize_uom

        return normalize_uom(value)
    # Retain SKU punctuation and numeric precision: no fuzzy price/SKU forgiveness.
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def evaluate(expected, extracted, document_id):
    fields = defaultdict(
        lambda: {
            "correct": 0,
            "exact": 0,
            "total": 0,
            "present_correct": 0,
            "present_total": 0,
            "null_correct": 0,
            "null_total": 0,
        }
    )
    errors = []
    critical_correct = critical_total = 0

    def compare(key, wanted, actual, location, ref=None, extra_line=False):
        nonlocal critical_correct, critical_total
        correct = not extra_line and extracted is not None and normalized(key, wanted) == normalized(key, actual)
        score = fields[key]
        score["total"] += 1
        score["correct"] += int(correct)
        score["exact"] += int(
            not extra_line and extracted is not None and type(wanted) is type(actual) and wanted == actual
        )
        group = "null" if wanted is None else "present"
        score[group + "_total"] += 1
        score[group + "_correct"] += int(correct)
        if key in CRITICAL:
            critical_total += 1
            critical_correct += int(correct)
        if not correct:
            code = (
                "SCHEMA_ERROR"
                if extracted is None
                else "HALLUCINATED_FIELD"
                if wanted is None
                else "MISSING_FIELD"
                if actual is None
                else CODES[key]
            )
            if key == "unit_price" and wanted is not None and actual is not None:
                try:
                    ratio = Decimal(str(actual)) / Decimal(str(wanted))
                    if ratio in {Decimal("0.01"), Decimal("0.1"), Decimal("10"), Decimal("100")}:
                        code = "DECIMAL_ERROR"
                except (InvalidOperation, ZeroDivisionError):
                    pass
            errors.append(
                {
                    "document_id": document_id,
                    "field": location,
                    "expected": wanted,
                    "extracted": actual,
                    "error_type": "TABLE_ASSOCIATION_ERROR" if extra_line else code,
                    "source_page": (ref or {}).get("page"),
                    "investigation": "Inspect original source and parsed row; verify label/column association before changing prompts.",
                }
            )

    for key in QUOTE_FIELDS:
        compare(
            key,
            expected.get(key),
            (extracted or {}).get(key),
            key,
            (extracted or {}).get("source_references", {}).get(key),
        )
    remaining = list(enumerate((extracted or {}).get("line_items", [])))
    associated = 0
    for i, line in enumerate(expected["line_items"]):
        matching = [
            (j, value)
            for j, value in remaining
            if normalized("supplier_sku", value.get("supplier_sku"))
            == normalized("supplier_sku", line.get("supplier_sku"))
        ]
        chosen = (
            matching[0]
            if matching
            else next(((j, v) for j, v in remaining if j == i), remaining[0] if remaining else (-1, {}))
        )
        j, actual = chosen
        if chosen in remaining:
            remaining.remove(chosen)
        associated += int(
            bool(matching)
            and all(
                normalized(k, line.get(k)) == normalized(k, actual.get(k)) for k in ("quantity", "unit_price", "uom")
            )
        )
        for key in LINE_FIELDS:
            compare(
                key,
                line.get(key),
                actual.get(key),
                f"line_items.{i}.{key}",
                actual.get("source_references", {}).get(key),
            )
    for _, extra in remaining:
        for key in LINE_FIELDS:
            compare(key, None, extra.get(key), "extra_line." + key, extra_line=True)
    return {
        "fields": dict(fields),
        "critical_correct": critical_correct,
        "critical_total": critical_total,
        "association_correct": associated,
        "association_total": len(expected["line_items"]) + len(remaining),
        "errors": errors,
    }
