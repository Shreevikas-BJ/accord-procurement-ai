"""Field-specific source facts. Model values never make their own evidence.

An intentionally conservative boundary: unrecognized layouts produce abstention,
not nearby-number matching. Raw source quotations are retained verbatim.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .schemas import Evidence
from .source_evidence import number

CRITICAL_QUOTE = ("supplier_name", "currency")
CRITICAL_LINE = ("supplier_sku", "quantity", "uom", "unit_price")
QUOTE_FIELDS = (
    *CRITICAL_QUOTE,
    "quote_number",
    "rfq_number",
    "shipping_cost",
    "tax",
    "stated_subtotal",
    "stated_total",
    "quote_date",
    "expiration_date",
    "payment_terms",
)
LINE_FIELDS = (*CRITICAL_LINE, "moq", "lead_time_days", "lead_time_min", "delivery_date", "stated_line_total")
NUMBERS = {
    "quantity",
    "unit_price",
    "moq",
    "shipping_cost",
    "tax",
    "stated_subtotal",
    "stated_total",
    "stated_line_total",
}
ALIASES = {
    "supplier_name": ["supplier", "supplier name", "seller", "vendor"],
    "currency": ["currency", "settlement currency", "currency choices"],
    "quote_number": ["quote", "quote number", "quotation number", "quotation no"],
    "rfq_number": ["rfq", "rfq number"],
    "supplier_sku": ["sku", "supplier sku", "part number", "item number"],
    "quantity": ["qty", "quantity", "quoted quantity", "order qty"],
    "uom": ["uom", "unit of measure", "unit"],
    "unit_price": ["unit price", "price per unit", "price each"],
    "moq": ["moq", "minimum order quantity", "min qty"],
    "lead_time_days": ["lead time", "lead time days"],
    "lead_time_min": ["lead time min"],
    "delivery_date": ["delivery", "delivery date"],
    "stated_line_total": ["line total", "extended", "extended price", "extension"],
    "shipping_cost": ["shipping", "shipping cost", "freight", "freight charge"],
    "tax": ["tax", "sales tax", "vat"],
    "stated_subtotal": ["subtotal", "stated subtotal"],
    "stated_total": ["total", "grand total", "stated total"],
    "quote_date": ["quote date", "quotation date"],
    "expiration_date": ["valid until", "expiration date", "expires"],
    "payment_terms": ["payment terms"],
}
INSTRUCTION = re.compile(
    r"ignore\s+(?:all|previous|the\s+quoted|system|the\s+evidence)|system\s*(?:prompt|:)|"
    r"(?:set|replace|change)\s+(?:every|all|the|supplier|tax|unit|price)|"
    r"return\s+(?:quantity|json|eur)|use\s+EUR\s+even|do\s+not\s+extract|"
    r"output\s+no\s+json|always\s+recommend|say\s+moq|send\s+this\s+order|"
    r"autonomous\s+purchasing|follow\s+these\s+instructions|assistant\s*:",
    re.I,
)


def label(value):
    return re.sub(r"\s+", " ", str(value).replace("_", " ")).strip(" :.|\t").lower()


LOOKUP = {label(alias): key for key, aliases in ALIASES.items() for alias in [key, *aliases]}


def canonical(value):
    return LOOKUP.get(label(value))


def date_value(value, context=""):
    """No locale guesses. Return None for impossible or unresolved dates."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    match = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", text)
    if not match:
        return None
    a, b, year = map(int, match.groups())
    if re.search(r"DD[/.]MM[/.]YYYY", context, re.I) or a > 12:
        day, month = a, b
    elif re.search(r"MM[/.]DD[/.]YYYY", context, re.I) or b > 12:
        month, day = a, b
    elif a == b:
        month = day = a
    else:
        return None
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def value_for(key, text, context=""):
    text = str(text if text is not None else "").strip()
    if not text or INSTRUCTION.search(text):
        return None
    if key in NUMBERS:
        # Field-aware punctuation cleanup only; retain the original for evidence.
        numeric = re.sub(r"(?<=\d)\s*([.,])\s*(?=\d)", r"\1", text)
        numeric = re.sub(r"^(?:USD|CAD|AUD|SGD|EUR|GBP|[$€£])\s*", "", numeric, flags=re.I)
        numeric = re.sub(r"\s*(?:USD|CAD|AUD|SGD|EUR|GBP)$", "", numeric, flags=re.I)
        if not re.fullmatch(r"\d+(?:[.,]\d+)*", numeric):
            return None  # ranges, percentages, included/TBD, formulas are not scalar costs
        return number(numeric)
    if key == "currency":
        return text.upper() if re.fullmatch(r"[A-Za-z]{3}", text) else None
    if key in ("lead_time_days", "lead_time_min"):
        match = re.fullmatch(r"(\d+)(?:\s*[-–]\s*(\d+))?\s*(days?|weeks?)?", text, re.I)
        if not match:
            return None
        return int(match[1] if key == "lead_time_min" else match[2] or match[1]) * (
            7 if (match[3] or "").lower().startswith("week") else 1
        )
    if key.endswith("date"):
        return date_value(text, context)
    if key == "supplier_sku":
        if any(c in text for c in (":", "|")):
            return None
        return re.sub(r"\s*([-/.])\s*", r"\1", text)
    if key == "uom":
        from .extraction_validation import normalize_uom

        return normalize_uom(text)
    return text


@dataclass
class Fact:
    key: str
    value: object
    raw: str
    page: int | None
    sheet: str | None = None
    row: int | None = None
    cell: str | None = None

    def reference(self, document):
        return Evidence(
            source_text=self.raw[:4000],
            page=self.page,
            evidence_type="ocr" if self.page in document.image_pages else "text",
            confidence=Decimal("0.85"),
            evidence_strength="strong",
            source_status="PRESENT",
            sheet=self.sheet,
            row=self.row,
            cell=self.cell,
        )


@dataclass
class SourceFacts:
    quote: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)
    instruction_rows: list = field(default_factory=list)


def source_facts(document):
    result = SourceFacts()
    current = None
    headers = None
    last_sheet = None
    context = "\n".join(row for row in document.text.splitlines() if not INSTRUCTION.search(row))

    def add(key, text, raw, page, sheet=None, row=None, column=None):
        nonlocal current
        if key == "supplier_sku":
            current = {}
            result.lines.append(current)
        if key in LINE_FIELDS:
            if current is None:
                return
            target = current
        else:
            target = result.quote
        fact = Fact(
            key,
            value_for(key, text, context),
            raw,
            page,
            sheet,
            row,
            f"{sheet}!{column}{row}" if sheet and column and row else None,
        )
        target.setdefault(key, []).append(fact)
        if key == "lead_time_days" and re.search(r"\d\s*[-–]\s*\d", str(text)):
            target.setdefault("lead_time_min", []).append(
                Fact("lead_time_min", value_for("lead_time_min", text), raw, page, sheet, row)
            )

    for page, text in (document.pages or {None: document.text}).items():
        for raw in text.splitlines():
            if INSTRUCTION.search(raw):
                result.instruction_rows.append({"page": page, "source_text": raw[:4000]})
                continue
            if re.search(r"(?:--- LINE ITEM ---|QUOTED LINE|^\s*quoted item\b)", raw, re.I):
                current = None
                headers = None
                continue
            try:
                obj = json.loads(raw)
                cells = obj.get("cells") if isinstance(obj, dict) else None
            except ValueError:
                cells = None
            if cells is not None:
                sheet, row = obj.get("sheet"), obj.get("row")
                if sheet != last_sheet:
                    headers = None
                    current = None
                    last_sheet = sheet
                if isinstance(cells, dict):
                    pairs = [(canonical(k), v, i) for i, (k, v) in enumerate(cells.items())]
                    # SKU must establish the row even when columns are reordered.
                    for key, val, column in sorted(pairs, key=lambda p: p[0] != "supplier_sku"):
                        if key:
                            add(key, val, raw, page, sheet, row, column_name(column))
                    continue
                parts = cells
                separator = "cells"
                if len(cells) == 1 and isinstance(cells[0], str):
                    match = re.match(r"^\s*([^:|]{1,60})\s*[:|]\s*(.*?)\s*$", cells[0])
                    if match and canonical(match[1]):
                        add(canonical(match[1]), match[2], raw, page, sheet, row, "A")
                    continue
            else:
                sheet = row = None
                parts = [p.strip() for p in re.split(r"\s*\|\s*|\s+:\s+|\s{2,}", raw.strip())]
                separator = "table"
            keys = [canonical(p) for p in parts]
            if "supplier_sku" in keys and sum(k is not None for k in keys) >= 3:
                headers = keys
                current = None
                continue
            if separator == "cells" and len(parts) >= 2 and canonical(parts[0]):
                add(canonical(parts[0]), parts[1], raw, page, sheet, row, "B")
                continue
            # Labeled text takes precedence over an older table header.
            match = re.match(r"^\s*([^:|]{1,60})\s*[:|]\s*(.*?)\s*$", raw)
            if match and canonical(match[1]):
                add(canonical(match[1]), match[2], raw, page)
                continue
            if match and current and label(match[1]).startswith("delivery date for "):
                sku = unique_fact(current.get("supplier_sku", []))
                if sku and label(match[1])[len("delivery date for ") :] == str(sku.value).lower():
                    add("delivery_date", match[2], raw, page)
                    continue
            if headers and len(parts) == len(headers):
                for i in sorted(range(len(headers)), key=lambda i: headers[i] != "supplier_sku"):
                    if headers[i]:
                        add(headers[i], parts[i], raw, page, sheet, row, column_name(i))
    return result


def column_name(index):
    value = ""
    while index >= 0:
        value = chr(index % 26 + 65) + value
        index = index // 26 - 1
    return value


def equivalent(key, actual, wanted):
    if actual is None or wanted is None:
        return actual is wanted
    if key in NUMBERS:
        try:
            parsed = Decimal(str(actual))
            return parsed.is_finite() and parsed == wanted
        except InvalidOperation:
            return False
    if key == "uom":
        return value_for(key, actual) == value_for(key, wanted)
    return str(actual).strip().casefold() == str(wanted).strip().casefold()


def unique_fact(facts):
    # An explicit blank/ambiguous cell conflicts with a concrete repeated field.
    if not facts or any(f.value is None for f in facts):
        return None
    return facts[0] if all(equivalent(facts[0].key, f.value, facts[0].value) for f in facts) else None


def line_sources(quote, source):
    remaining = list(enumerate(source.lines))
    for index, line in enumerate(quote.line_items):
        match = next(
            (
                (i, fields)
                for i, fields in remaining
                if (f := unique_fact(fields.get("supplier_sku", [])))
                and equivalent("supplier_sku", line.supplier_sku, f.value)
            ),
            None,
        )
        if match is None:
            match = next(((i, fields) for i, fields in remaining if i == index), None)
        if match:
            remaining.remove(match)
        yield index, line, match[1] if match else {}


def verification_requests(quote, document):
    source = source_facts(document)
    requests = []
    # Suspected injected documents abstain; never ask the model to reinterpret an attack.
    if source.instruction_rows:
        return []
    for index, line, fields in line_sources(quote, source):
        for key in ("unit_price", "quantity"):
            fact = unique_fact(fields.get(key, []))
            actual = getattr(line, key)
            if actual is not None and fact and not equivalent(key, actual, fact.value):
                requests.append(
                    {
                        "field": f"line_items.{index}.{key}",
                        "sku": line.supplier_sku,
                        "source": fact.raw,
                        "page": fact.page,
                        "expected_type": key,
                    }
                )
    return requests[:2]


def harden_quote(quote, document):
    """Gate model facts; preserve originals in diagnostics before any mutation."""
    source = source_facts(document)
    original = quote.model_dump(mode="json")
    findings, assessments, changes = [], {}, []
    verified = document.metadata.get("field_verification", {})

    def flag(code, path, message):
        findings.append({"code": code, "field": path, "message": message})

    def accept(obj, fields, keys, prefix=""):
        for key in keys:
            path = prefix + key
            actual = getattr(obj, key)
            candidates = fields.get(key, [])
            fact = unique_fact(candidates)
            accepted = fact is not None and (actual is None or equivalent(key, actual, fact.value))
            verification = verified.get(path)
            if not accepted and fact and verification:
                accepted = (
                    equivalent(key, verification.get("value"), fact.value)
                    and verification.get("source_text") == fact.raw
                )
                if not accepted:
                    flag("SECOND_PASS_DISAGREEMENT", path, "Focused verification did not resolve the source conflict.")
            # For detected instruction text, do not emit any model-derived facts.
            # Independent labeled source facts can still be presented, but conflicting
            # model answers remain null. This is source acceptance, not prompt trust.
            if accepted:
                value = fact.value
                if key.endswith("date"):
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                setattr(obj, key, value)
                obj.source_references[key] = fact.reference(document)
                assessments[path] = {"status": "PRESENT", "strength": "strong", "accepted": True}
                if actual is None or not equivalent(key, actual, fact.value):
                    changes.append(
                        {
                            "field": path,
                            "original": str(actual) if actual is not None else None,
                            "accepted": str(fact.value),
                            "reason": "explicit_source" if actual is None else "focused_verification_with_source",
                        }
                    )
            else:
                status = "AMBIGUOUS" if candidates else "NOT_FOUND"
                if actual is not None:
                    flag(
                        "UNSUPPORTED_EXTRACTED_VALUE",
                        path,
                        "The extracted value lacks field-specific source support and was withheld.",
                    )
                    changes.append({"field": path, "original": str(actual), "accepted": None, "reason": status})
                if candidates:
                    flag(
                        "SOURCE_VALUE_CONFLICT",
                        path,
                        "Source values are conflicting, ambiguous, or differ from extraction.",
                    )
                setattr(obj, key, None)
                obj.source_references[key] = Evidence(
                    source_text=candidates[0].raw[:4000] if candidates else "",
                    page=candidates[0].page if candidates else None,
                    confidence=0,
                    evidence_type="missing",
                    evidence_strength="unsupported",
                    source_status=status,
                )
                assessments[path] = {"status": status, "strength": "unsupported", "accepted": False}
            if key == "currency" and not accepted:
                flag(
                    "CURRENCY_REVIEW_REQUIRED", path, "Settlement currency needs an explicit, unambiguous source code."
                )
            if key.endswith("date") and candidates and not accepted:
                flag("DATE_REVIEW_REQUIRED", path, "Date is invalid, ambiguous, or unsupported by the source.")

    accept(quote, source.quote, QUOTE_FIELDS)
    for index, line, fields in line_sources(quote, source):
        if (
            line.quantity is not None
            and not unique_fact(fields.get("quantity", []))
            and any(
                equivalent("quantity", line.quantity, f.value) for f in fields.get("moq", []) if f.value is not None
            )
        ):
            flag(
                "QUANTITY_MOQ_AMBIGUITY",
                f"line_items.{index}.quantity",
                "Minimum order quantity is not evidence of quoted quantity.",
            )
        accept(line, fields, LINE_FIELDS, f"line_items.{index}.")
    if len(source.lines) != len(quote.line_items):
        flag(
            "SOURCE_LINE_COUNT_MISMATCH",
            "line_items",
            "Extracted rows differ from identifiable source rows; check omitted or repeated lots.",
        )
    if source.instruction_rows:
        flag(
            "DOCUMENT_INSTRUCTION_TEXT_DETECTED",
            "document",
            "Document contains unusual instruction text. Critical values require review.",
        )
        # Unmodeled free-form fields can carry action requests or fabricated facts.
        quote.supplier_email = quote.notes = quote.shipping_terms = None
        for line in quote.line_items:
            line.price_tiers = []
    if quote.shipping_cost is None or quote.tax is None:
        flag(
            "TOTAL_COST_INCOMPLETE",
            "shipping_cost",
            "Freight or tax is unknown; total-cost comparison remains incomplete.",
        )
    # Revalidate deterministic candidates against the same precision/storage constraints.
    from .schemas import QuoteExtraction

    validated = QuoteExtraction.model_validate(quote.model_dump())
    for key in type(quote).model_fields:
        setattr(quote, key, getattr(validated, key))
    return {
        "original_ai_payload": original,
        "evidence_assessments": assessments,
        "source_adjustments": changes,
        "safety_findings": findings,
        "instruction_signal_count": len(source.instruction_rows),
    }
