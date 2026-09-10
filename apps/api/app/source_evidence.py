"""Attach only source text that can be located and supports the extracted value.

This module never changes any extracted commercial value or invents a quotation.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from .schemas import Evidence

ALIASES = {
    "supplier_name": ("supplier_name", "supplier", "vendor", "seller"),
    "quote_number": ("quote_number", "quote number", "quote", "quotation"),
    "currency": ("currency",),
    "supplier_sku": ("supplier_sku", "sku", "part number"),
    "quantity": ("quantity", "qty"),
    "unit_price": ("unit_price", "unit price", "price per unit"),
    "uom": ("uom", "unit of measure"),
    "moq": ("moq", "minimum order quantity"),
    "lead_time_days": ("lead_time_days", "lead time"),
    "delivery_date": ("delivery_date", "delivery", "delivery date"),
    "shipping_cost": ("shipping_cost", "shipping"),
    "tax": ("tax",),
}


def number(token):
    token = token.strip()
    if "," in token and "." in token:
        token = (
            token.replace(",", "") if token.rfind(".") > token.rfind(",") else token.replace(".", "").replace(",", ".")
        )
    elif "," in token:
        token = token.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", token) else token.replace(",", ".")
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def supports(field, value, text):
    if value is None:
        return False
    # Spreadsheet row metadata is not evidence for a commercial amount.
    # Match cell contents, including a column-specific value when available.
    try:
        cells = json.loads(text).get("cells")
        aliases = ALIASES.get(field, (field,))
        if isinstance(cells, dict):
            matched = [v for k, v in cells.items() if k.strip().lower() in aliases]
            text = json.dumps(matched if matched else list(cells.values()))
        elif isinstance(cells, list):
            text = json.dumps(cells[1:] if cells and str(cells[0]).strip().lower() in aliases else cells)
    except (ValueError, AttributeError):
        pass
    if field in {"quantity", "unit_price", "moq", "shipping_cost", "tax"}:
        tokens = re.findall(r"(?<![\w.-])\d+(?:[.,]\d+)*(?![\w.-])", text)
        return Decimal(str(value)) in [number(t) for t in tokens]
    if field == "lead_time_days":
        explicit = re.search(
            r"lead[_ ]time(?:_days)?\s*[:|,]\s*(\d+)(?:\s*[-–]\s*(\d+))?\s*(days?|weeks?)?", text, re.I
        )
        if explicit:
            return (
                int(explicit[2] or explicit[1]) * (7 if (explicit[3] or "").lower().startswith("week") else 1) == value
            )
        return any(
            int(high or low) * (7 if unit.lower().startswith("week") else 1) == value
            for low, high, unit in re.findall(r"\b(\d+)(?:\s*[-–]\s*(\d+))?\s*(days?|weeks?)\b", text, re.I)
        )
    if field == "uom":
        from .extraction_validation import normalize_uom

        return any(normalize_uom(token) == normalize_uom(value) for token in re.findall(r"\b\w+\b", text))
    return bool(re.search(r"(?<![\w])" + re.escape(str(value)) + r"(?![\w])", text, re.I))


def row_label(text):
    try:
        cells = json.loads(text).get("cells")
        if isinstance(cells, list) and cells:
            return str(cells[0]).strip().lower()
    except (ValueError, AttributeError):
        pass
    return re.split(r"[:|,]", text, maxsplit=1)[0].strip().lower()


def derive_references(quote, document):
    pages = document.pages or {None: document.text}
    source_rows = [(page, row) for page, text in pages.items() for row in text.splitlines() if row.strip()]

    def attach(obj, fields, candidates):
        for field in fields:
            value = getattr(obj, field)
            if value is None:
                continue
            existing = obj.source_references.get(field)
            if (
                existing
                and existing.page is not None
                and existing.page not in pages
                and existing.page not in document.image_pages
            ):
                continue
            if (
                existing
                and supports(field, value, existing.source_text)
                and any(existing.page == page and existing.source_text in text for page, text in pages.items())
            ):
                continue
            labeled = []
            for page, text in candidates:
                aliases = ALIASES.get(field, (field,))
                if row_label(text) in aliases:
                    labeled.append((page, text))
            # Labeled blocks use field-specific rows. Single tabular rows are
            # located by SKU and retained verbatim for buyer column inspection.
            matches = [(page, text) for page, text in (labeled or candidates) if supports(field, value, text)]
            if matches:
                page, text = matches[0]
                obj.source_references[field] = Evidence(
                    page=page,
                    source_text=text[:4000],
                    confidence=Decimal("0.8"),
                    evidence_type="ocr" if page in document.image_pages else "text",
                )
            elif len(document.image_pages) == 1:
                obj.source_references[field] = Evidence(
                    page=document.image_pages[0], source_text="", confidence=Decimal("0.5"), evidence_type="visual"
                )

    attach(quote, ("supplier_name", "quote_number", "currency", "shipping_cost", "tax"), source_rows)
    consumed = {}
    for line in quote.line_items:
        indices = [
            i
            for i, (_, row) in enumerate(source_rows)
            if line.supplier_sku and supports("supplier_sku", line.supplier_sku, row)
        ]
        occurrence = consumed.get(line.supplier_sku, 0)
        candidates = []
        if indices:
            start = indices[min(occurrence, len(indices) - 1)]
            consumed[line.supplier_sku] = occurrence + 1
            first = source_rows[start]
            if row_label(first[1]) in ALIASES["supplier_sku"]:
                end = start + 1
                while end < len(source_rows):
                    row = source_rows[end][1]
                    if (
                        "LINE ITEM" in row
                        or row_label(row).startswith(("quoted item", "subtotal", "grand total", "shipping", "tax"))
                        or row_label(row) in ALIASES["supplier_sku"]
                    ):
                        break
                    end += 1
                candidates = source_rows[start:end]
            else:
                candidates = [first]
        attach(
            line,
            ("supplier_sku", "quantity", "uom", "unit_price", "moq", "lead_time_days", "delivery_date"),
            candidates,
        )
