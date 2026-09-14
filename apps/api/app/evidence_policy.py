"""Field-specific source facts. Model values never make their own evidence.

An intentionally conservative boundary: unrecognized layouts produce abstention,
not nearby-number matching. Raw source quotations are retained verbatim.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .schemas import Evidence, LineItemExtraction, PriceTier
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
LINE_FIELDS = (
    *CRITICAL_LINE,
    "description",
    "moq",
    "lead_time_days",
    "lead_time_min",
    "delivery_date",
    "stated_line_total",
)
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
    "rfq_number": ["rfq", "rfq number", "tfq"],
    "supplier_sku": [
        "sku",
        "supplier sku",
        "supplier part number",
        "supplier part no",
        "vendor part number",
        "vendor part no",
        "part number",
        "part no",
        "item number",
        "item no",
        "item code",
        "material",
        "stock no",
    ],
    "description": ["description", "item description", "product description"],
    "quantity": ["qty", "oty", "quantity", "quoted quantity", "order qty", "order quantity"],
    "uom": ["uom", "yom", "vom", "unit of measure", "unit"],
    "unit_price": ["unit price", "price per unit", "price each", "each price", "unit cost", "net ea", "net ea."],
    "moq": ["moq", "moqg", "minimum order quantity", "minimum qty", "min qty"],
    "lead_time_days": ["lead time", "lead time days", "lead", "availability"],
    "lead_time_min": ["lead time min"],
    "delivery_date": ["delivery", "delivery date", "ship date", "promise date"],
    "stated_line_total": ["line total", "extended", "extended price", "extension", "amount"],
    "shipping_cost": ["shipping", "shipping cost", "shipping & handling", "shipping and handling", "freight", "freight charge"],
    "tax": ["tax", "sales tax", "vat", "gst"],
    "stated_subtotal": ["subtotal", "sub total", "stated subtotal"],
    "stated_total": ["total", "grand total", "amount due", "stated total"],
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
    return re.sub(r"[^a-z0-9]+", " ", str(value).replace("_", " ").casefold()).strip()


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
        value = text.upper()
        return value if re.fullmatch(r"[A-Za-z]{3}", text) and value not in {"TBD", "N/A"} else None
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
    table: int | None = None
    bounding_box: list[float] | None = None
    confidence: str = "strong"

    def reference(self, document, *, decision_status="ACCEPTED", reason="Explicit field-specific source evidence.", raw_candidate=None):
        return Evidence(
            source_text=self.raw[:4000],
            page=self.page,
            evidence_type="ocr" if self.page in document.image_pages else "text",
            confidence=Decimal("0.85") if self.confidence == "strong" else Decimal("0.6"),
            bounding_box=self.bounding_box,
            evidence_strength=self.confidence,
            source_status="PRESENT",
            sheet=self.sheet,
            row=self.row,
            cell=self.cell,
            table=self.table,
            decision_status=decision_status,
            reason=reason,
            raw_candidate=str(raw_candidate) if raw_candidate is not None else None,
            accepted_value=str(self.value) if decision_status == "ACCEPTED" and self.value is not None else None,
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

    def start_line():
        nonlocal current
        current = {}
        result.lines.append(current)

    def add(
        key,
        text,
        raw,
        page,
        sheet=None,
        row=None,
        column=None,
        table=None,
        bounding_box=None,
        confidence="strong",
        establish=True,
    ):
        nonlocal current
        if key == "supplier_sku" and establish:
            start_line()
        if key in LINE_FIELDS:
            if current is None:
                return
            target = current
        else:
            target = result.quote
        parsed_value = value_for(key, text, context)
        if key == "supplier_name" and page in document.image_pages and parsed_value:
            # Tesseract occasionally separates the first capital from the rest
            # of a proper supplier word (for example, ``J uniper``). The
            # lowercase continuation makes this narrower than ordinary initials.
            parsed_value = re.sub(r"^([A-Z])\s+([a-z]{3,})(?=\s|$)", r"\1\2", str(parsed_value))
        fact = Fact(
            key,
            parsed_value,
            raw,
            page,
            sheet,
            row,
            f"{sheet}!{column}{row}" if sheet and column and row else None,
            table,
            bounding_box,
            confidence,
        )
        target.setdefault(key, []).append(fact)
        if key == "lead_time_days" and re.search(r"\d\s*[-–]\s*\d", str(text)):
            target.setdefault("lead_time_min", []).append(
                Fact("lead_time_min", value_for("lead_time_min", text), raw, page, sheet, row)
            )

    # Prefer format-specific physical rows where deterministic structure exists.
    # Raw text remains available below for quote-level labels and fallback parsing.
    structured_signatures = set()
    structured_positions = set()
    for candidate in getattr(document, "structured_rows", []):
        fields = candidate.get("field_cells") or {}
        if not fields or candidate.get("layout_confidence") == "header":
            continue
        line_values = {
            key: cell
            for key, cell in fields.items()
            if key in LINE_FIELDS and isinstance(cell, dict)
        }
        parsed = {
            key: value_for(key, cell.get("value"), context)
            for key, cell in line_values.items()
        }
        sku = parsed.get("supplier_sku")
        credible_sku = bool(sku and re.search(r"\d", str(sku)) and canonical(sku) is None)
        credible_numbers = {key for key in ("quantity", "unit_price", "stated_line_total") if parsed.get(key) is not None}
        if not (
            (credible_sku and credible_numbers)
            or {"quantity", "unit_price"} <= credible_numbers
        ):
            continue
        start_line()
        raw = candidate.get("raw_text") or " | ".join(
            str(cell.get("value") or "") for cell in line_values.values()
        )
        structured_signatures.add(re.sub(r"\s+", " ", raw).strip().casefold())
        if candidate.get("sheet") and candidate.get("row"):
            structured_positions.add((candidate.get("sheet"), candidate.get("row")))
        for key in sorted(line_values, key=lambda value: value != "supplier_sku"):
            cell = line_values[key]
            cell_ref = cell.get("cell")
            column = None
            if cell_ref and "!" in cell_ref:
                column = re.sub(r"\d+$", "", cell_ref.rsplit("!", 1)[1])
            add(
                key,
                cell.get("value"),
                raw,
                candidate.get("page"),
                candidate.get("sheet"),
                candidate.get("row"),
                column,
                candidate.get("table"),
                cell.get("bbox") or candidate.get("bbox"),
                "strong" if candidate.get("layout_confidence") in {"strong", "table"} else "weak",
                establish=False,
            )

    inline_aliases = sorted(
        {
            alias
            for key in LINE_FIELDS
            for alias in (key, *ALIASES.get(key, []))
        },
        key=len,
        reverse=True,
    )
    inline_pattern = re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(alias).replace(r"\ ", r"\s+") for alias in inline_aliases) + r")\s*:?[ \t]*",
        re.I,
    )

    def inline_row(raw, page):
        if re.search(r"\b(?:withdrawn|previous offer|not current)\b", raw, re.I):
            return False
        matches = list(inline_pattern.finditer(raw))
        mapped = [(match, canonical(match.group(1))) for match in matches]
        mapped = [(match, key) for match, key in mapped if key in LINE_FIELDS]
        if len(mapped) < 2:
            return False
        values = []
        for index, (match, key) in enumerate(mapped):
            end = mapped[index + 1][0].start() if index + 1 < len(mapped) else len(raw)
            values.append((key, raw[match.end() : end].strip(" :|,;")))
        # A header row has labels but no values between them.
        if sum(bool(value) for _, value in values) < 2:
            return False
        prefix = raw[: mapped[0][0].start()].strip(" :|,;")
        start_line()
        if prefix:
            tokens = prefix.split()
            add("supplier_sku", tokens[0], raw, page, establish=False)
            if len(tokens) > 1:
                add("description", " ".join(tokens[1:]), raw, page, establish=False)
        for key, value in values:
            add(key, value, raw, page, establish=False)
        return True

    def add_tiers(raw, page):
        if current is None or not re.search(r"tier|\d\s*(?:[-–]|\+)", raw, re.I):
            return False
        matches = list(
            re.finditer(
                r"(\d[\d,]*(?:\.\d+)?)\s*(?:(?:[-–])\s*(\d[\d,]*(?:\.\d+)?)|(\+))\s*[:=]?\s*(?:USD|CAD|EUR|GBP|[$€£])?\s*(\d[\d,]*(?:\.\d+)?)",
                raw,
                re.I,
            )
        )
        if not matches:
            return False
        target = current
        named_sku = re.search(r"\bfor\s+([^:]+?)\s*:", raw, re.I)
        if named_sku:
            wanted = value_for("supplier_sku", named_sku.group(1))
            matches_by_sku = [
                fields
                for fields in result.lines
                if (fact := unique_fact(fields.get("supplier_sku", [])))
                and equivalent("supplier_sku", fact.value, wanted)
            ]
            if len(matches_by_sku) == 1:
                target = matches_by_sku[0]
        tiers = target.setdefault("_price_tiers", [])
        for match in matches:
            minimum = number(match[1])
            maximum = None if match[3] else number(match[2])
            price = number(match[4])
            if minimum is not None and price is not None:
                tiers.append(
                    {
                        "minimum": minimum,
                        "maximum": maximum,
                        "unit_price": price,
                        "fact": Fact("unit_price", price, raw, page),
                    }
                )
        return bool(tiers)

    for page, text in (document.pages or {None: document.text}).items():
        for raw in text.splitlines():
            if INSTRUCTION.search(raw):
                result.instruction_rows.append({"page": page, "source_text": raw[:4000]})
                continue
            signature = re.sub(r"\s+", " ", raw).strip().casefold()
            if signature in structured_signatures:
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
                if (sheet, row) in structured_positions:
                    continue
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
                    match = re.match(r"^\s*([^:|;.]{1,60})\s*[:|;.]\s*(.*?)\s*$", cells[0])
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
            if separator == "cells" and len(parts) >= 2 and current and label(parts[0]).startswith("delivery date for "):
                sku = unique_fact(current.get("supplier_sku", []))
                if sku and label(parts[0])[len("delivery date for ") :] == str(sku.value).casefold():
                    add("delivery_date", parts[1], raw, page, sheet, row, "B")
                continue
            if cells is not None:
                # The complete JSON candidate has already been interpreted as
                # cells. Never scan its property names as inline source labels.
                continue
            # Labeled text takes precedence over an older table header.
            match = re.match(r"^\s*([^:|;.]{1,60})\s*[:|;.]\s*(.*?)\s*$", raw)
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
                continue
            if add_tiers(raw, page):
                continue
            inline_row(raw, page)

    # A row extension is an independent arithmetic constraint. When OCR drops a
    # decimal point, accept total / quantity only when it reproduces the printed
    # extension to currency precision and the printed unit price does not.
    for fields in result.lines:
        row_facts = [fact for facts in fields.values() if isinstance(facts, list) for fact in facts if isinstance(fact, Fact)]
        if not row_facts or not any(fact.page in document.image_pages for fact in row_facts):
            continue
        quantity = unique_fact(fields.get("quantity", []))
        unit_price = unique_fact(fields.get("unit_price", []))
        line_total = unique_fact(fields.get("stated_line_total", []))
        if not line_total:
            continue
        if quantity and quantity.value and (not unit_price or unit_price.value is None):
            calculated = (line_total.value / quantity.value).quantize(Decimal("0.000001")).normalize()
            if storage_compatible("unit_price", calculated) and abs(
                quantity.value * calculated - line_total.value
            ) <= Decimal("0.02"):
                basis = (fields.get("unit_price") or [line_total])[0]
                fields["unit_price"] = [
                    Fact(
                        "unit_price", calculated, basis.raw, basis.page, basis.sheet, basis.row,
                        basis.cell, basis.table, basis.bounding_box, basis.confidence,
                    )
                ]
                unit_price = fields["unit_price"][0]
        if quantity and quantity.value and unit_price and unit_price.value is not None:
            direct_difference = abs(quantity.value * unit_price.value - line_total.value)
            if direct_difference > Decimal("0.02"):
                calculated = (line_total.value / quantity.value).quantize(Decimal("0.000001")).normalize()
                if storage_compatible("unit_price", calculated) and abs(
                    quantity.value * calculated - line_total.value
                ) <= Decimal("0.02"):
                    fields["unit_price"] = [
                        Fact(
                            "unit_price", calculated, unit_price.raw, unit_price.page, unit_price.sheet,
                            unit_price.row, unit_price.cell, unit_price.table, unit_price.bounding_box,
                            unit_price.confidence,
                        )
                    ]
        if (not quantity or quantity.value is None) and unit_price and unit_price.value:
            calculated_quantity = line_total.value / unit_price.value
            integral_quantity = calculated_quantity.to_integral_value()
            if calculated_quantity == integral_quantity and integral_quantity > 0:
                basis = (fields.get("quantity") or [line_total])[0]
                fields["quantity"] = [
                    Fact(
                        "quantity", integral_quantity, basis.raw, basis.page, basis.sheet, basis.row,
                        basis.cell, basis.table, basis.bounding_box, basis.confidence,
                    )
                ]
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


def storage_compatible(key, value):
    if value is None:
        return False
    if key in NUMBERS:
        try:
            decimal = Decimal(str(value))
        except InvalidOperation:
            return False
        places = max(0, -decimal.as_tuple().exponent)
        limit = 6 if key == "unit_price" else 4
        return decimal.is_finite() and places <= limit
    if key in ("lead_time_days", "lead_time_min"):
        return isinstance(value, int) and 0 <= value <= 3650
    if key.endswith("date"):
        return bool(value)
    return bool(str(value).strip())


def strong_fact(facts):
    fact = unique_fact(facts)
    return fact if fact and fact.confidence == "strong" else None


def source_line_viable(fields):
    keys = {key for key in CRITICAL_LINE if strong_fact(fields.get(key, []))}
    return {"quantity", "unit_price"} <= keys and bool(keys & {"supplier_sku", "uom"})


def reconcile_source_lines(quote, source):
    """Put model rows in physical source order and recover omitted source rows."""
    remaining = list(enumerate(quote.line_items))
    ordered = []
    recovered = []
    for source_index, fields in enumerate(source.lines):
        source_sku = strong_fact(fields.get("supplier_sku", []))
        match = None
        if source_sku:
            match = next(
                (
                    pair
                    for pair in remaining
                    if equivalent("supplier_sku", pair[1].supplier_sku, source_sku.value)
                ),
                None,
            )
        if match is None and remaining:
            # Source order is the bounded fallback for rows with an intentionally
            # blank SKU; it does not copy any values between rows.
            match = remaining[0]
        if match:
            remaining.remove(match)
            ordered.append(match[1])
        elif source_line_viable(fields):
            ordered.append(LineItemExtraction())
            recovered.append(source_index)
    ordered.extend(line for _, line in remaining)
    if ordered:
        quote.line_items = ordered
    return recovered


def apply_source_tiers(line, fields, document):
    tier_rows = fields.get("_price_tiers", [])
    if not tier_rows:
        return None
    tiers = []
    for row in tier_rows:
        try:
            tiers.append(
                PriceTier(
                    minimum=row["minimum"],
                    maximum=row["maximum"],
                    unit_price=row["unit_price"],
                )
            )
        except (ValueError, TypeError):
            return None
    line.price_tiers = tiers
    first = tier_rows[0]["fact"]
    line.source_references["price_tiers"] = first.reference(
        document,
        reason="Explicit quantity-tier source evidence.",
    )
    quantity = strong_fact(fields.get("quantity", []))
    if not quantity:
        return None
    applicable = [
        row
        for row in tier_rows
        if row["minimum"] <= quantity.value and (row["maximum"] is None or quantity.value <= row["maximum"])
    ]
    if len(applicable) != 1:
        return None
    selected = applicable[0]
    direct = strong_fact(fields.get("unit_price", []))
    total = strong_fact(fields.get("stated_line_total", []))
    arithmetic_match = bool(
        total
        and abs(quantity.value * selected["unit_price"] - total.value) <= Decimal("0.02")
    )
    if direct is None or equivalent("unit_price", direct.value, selected["unit_price"]) or arithmetic_match:
        return selected["fact"]
    return None


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
    recovered_rows = reconcile_source_lines(quote, source)

    def flag(code, path, message):
        findings.append({"code": code, "field": path, "message": message})

    def accept(obj, fields, keys, prefix=""):
        for key in keys:
            path = prefix + key
            actual = getattr(obj, key)
            candidates = fields.get(key, [])
            fact = strong_fact(candidates)
            accepted = fact is not None and storage_compatible(key, fact.value)
            # For detected instruction text, do not emit any model-derived facts.
            # Independent labeled source facts can still be presented, but conflicting
            # model answers remain null. This is source acceptance, not prompt trust.
            if accepted:
                value = fact.value
                if key.endswith("date"):
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                setattr(obj, key, value)
                obj.source_references[key] = fact.reference(document)
                assessments[path] = {
                    "status": "PRESENT",
                    "decision_status": "ACCEPTED",
                    "strength": "strong",
                    "raw_candidate": str(actual) if actual is not None else None,
                    "accepted_value": str(fact.value),
                    "reason": "Explicit field-specific source evidence passed deterministic checks.",
                }
                if actual is None or not equivalent(key, actual, fact.value):
                    changes.append(
                        {
                            "field": path,
                            "original": str(actual) if actual is not None else None,
                            "accepted": str(fact.value),
                            "reason": "explicit_source" if actual is None else "deterministic_source_override",
                        }
                    )
            else:
                source_value = next((candidate.value for candidate in candidates if candidate.value is not None), None)
                raw_candidate = actual if actual is not None else source_value
                if candidates and source_value is not None:
                    decision = "REVIEW_REQUIRED"
                    source_status = "AMBIGUOUS"
                    reason = (
                        "Source value exceeds supported storage precision; buyer verification is required."
                        if fact and not storage_compatible(key, fact.value)
                        else "Source evidence is plausible but its field or row association is not unambiguous."
                    )
                elif actual is not None:
                    decision = "REJECTED"
                    source_status = "NOT_FOUND"
                    reason = "The model candidate has no field-specific source support."
                else:
                    decision = "NOT_FOUND"
                    source_status = "NOT_FOUND"
                    reason = "No field-specific value was found in the selected source."
                if actual is not None:
                    flag(
                        "UNSUPPORTED_EXTRACTED_VALUE",
                        path,
                        "The extracted value lacks field-specific source support and was withheld.",
                    )
                    changes.append({"field": path, "original": str(actual), "accepted": None, "reason": decision})
                if candidates:
                    flag(
                        "SOURCE_VALUE_CONFLICT",
                        path,
                        "Source values are conflicting, ambiguous, or differ from extraction.",
                    )
                setattr(obj, key, None)
                if candidates:
                    candidate = candidates[0]
                    obj.source_references[key] = candidate.reference(
                        document,
                        decision_status=decision,
                        reason=reason,
                        raw_candidate=raw_candidate,
                    )
                    obj.source_references[key].source_status = source_status
                    obj.source_references[key].evidence_strength = "weak" if decision == "REVIEW_REQUIRED" else "unsupported"
                    obj.source_references[key].confidence = Decimal("0.6") if decision == "REVIEW_REQUIRED" else Decimal("0")
                    obj.source_references[key].accepted_value = None
                else:
                    obj.source_references[key] = Evidence(
                        source_text="",
                        confidence=0,
                        evidence_type="missing",
                        evidence_strength="unsupported",
                        source_status=source_status,
                        decision_status=decision,
                        reason=reason,
                        raw_candidate=str(raw_candidate) if raw_candidate is not None else None,
                    )
                assessments[path] = {
                    "status": source_status,
                    "decision_status": decision,
                    "strength": obj.source_references[key].evidence_strength,
                    "accepted": False,
                    "raw_candidate": str(raw_candidate) if raw_candidate is not None else None,
                    "accepted_value": None,
                    "reason": reason,
                }
            if key == "currency" and not accepted:
                flag(
                    "CURRENCY_REVIEW_REQUIRED", path, "Settlement currency needs an explicit, unambiguous source code."
                )
            if key.endswith("date") and candidates and not accepted:
                flag("DATE_REVIEW_REQUIRED", path, "Date is invalid, ambiguous, or unsupported by the source.")

    accept(quote, source.quote, QUOTE_FIELDS)
    for index, line, fields in line_sources(quote, source):
        tier_price = apply_source_tiers(line, fields, document)
        if tier_price:
            fields = dict(fields)
            fields["unit_price"] = [tier_price]
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
    if recovered_rows:
        findings.append(
            {
                "code": "SOURCE_ROWS_RECOVERED",
                "field": "line_items",
                "message": f"Recovered {len(recovered_rows)} physical source row(s) omitted by semantic extraction.",
            }
        )
    # Revalidate deterministic candidates against the same precision/storage constraints.
    from .schemas import QuoteExtraction

    validated = QuoteExtraction.model_validate(quote.model_dump())
    for key in type(quote).model_fields:
        setattr(quote, key, getattr(validated, key))
    return {
        "original_ai_payload": original,
        "evidence_assessments": assessments,
        "field_decisions": assessments,
        "source_adjustments": changes,
        "safety_findings": findings,
        "instruction_signal_count": len(source.instruction_rows),
        "source_row_count": len(source.lines),
        "recovered_source_rows": recovered_rows,
    }
