"""Generate the sealed Phase 2.7 unseen-layout holdout deterministically."""

import csv
import hashlib
import json
import random
import subprocess
import tempfile
from pathlib import Path

from openpyxl import Workbook
from PIL import Image, ImageEnhance
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


ROOT = Path("/work/benchmark-data/phase27-holdout")
DOCS, TRUTH = ROOT / "documents", ROOT / "ground-truth"
DOCS.mkdir(parents=True, exist_ok=True)
TRUTH.mkdir(parents=True, exist_ok=True)
random.seed(2707)
SUPPLIERS = ["Aster Motion Works", "Blue Mesa Components", "Copper Ridge Supply", "Desert Signal Partners", "Evergreen Controls"]
CURRENCIES = ["USD", "EUR", "GBP", "CAD", "USD"]
HEADER_ORDERS = [
    [("supplier_sku", "Vendor Part No"), ("description", "Item Narrative"), ("quantity", "Order Quantity"), ("uom", "Unit of Measure"), ("unit_price", "Price Each"), ("stated_line_total", "Extension")],
    [("description", "Product Description"), ("supplier_sku", "Stock No"), ("uom", "UOM"), ("quantity", "Quoted Quantity"), ("stated_line_total", "Amount"), ("unit_price", "Net Ea")],
    [("quantity", "Qty"), ("supplier_sku", "Supplier Part Number"), ("description", "Description"), ("unit_price", "Unit Cost"), ("uom", "Unit"), ("stated_line_total", "Line Total")],
]


def data(index):
    supplier = SUPPLIERS[index % len(SUPPLIERS)]
    currency = CURRENCIES[index % len(CURRENCIES)]
    repeated = index % 11 == 0
    sku1 = f"AX-{700 + index:03d}/B"
    sku2 = sku1 if repeated else f"NC/H{index:02d}-1"
    qty1, qty2 = 1000 + index * 3, 25 + index
    price1, price2 = 4.72 + (index % 4) * 0.11, 6.10 + (index % 5) * 0.07
    lines = [
        {"supplier_sku": sku1, "description": "Industrial relay with mounting bracket", "quantity": str(qty1), "uom": "EA", "unit_price": f"{price1:.2f}", "moq": "500", "lead_time_days": 14, "delivery_date": "2026-10-20", "stated_line_total": f"{qty1*price1:.2f}"},
        {"supplier_sku": sku2, "description": "Shielded control harness, low smoke", "quantity": str(qty2), "uom": "PCS", "unit_price": f"{price2:.2f}", "moq": "10", "lead_time_days": 21, "delivery_date": "2026-10-27", "stated_line_total": f"{qty2*price2:.2f}"},
    ]
    return {
        "supplier_name": supplier, "quote_number": f"P27-{index:03d}-Q", "rfq_number": f"RFQ-27-{index:03d}",
        "currency": currency, "quote_date": "2026-09-13", "expiration_date": "2026-11-30",
        "shipping_cost": "18.50", "tax": "0", "line_items": lines,
        "stated_subtotal": f"{sum(float(line['stated_line_total']) for line in lines):.2f}",
        "stated_total": f"{sum(float(line['stated_line_total']) for line in lines)+18.5:.2f}",
        "payment_terms": "Net 30", "shipping_terms": "FOB origin",
    }


def rows(truth, order):
    result = []
    for line in truth["line_items"]:
        result.append([line[key] for key, _ in order])
    return result


def draw_pdf(path, truth, index):
    order = HEADER_ORDERS[index % len(HEADER_ORDERS)]
    c = canvas.Canvas(str(path), pagesize=letter)
    if index % 5 == 0:
        c.drawString(55, 735, "Technical notes and packing instructions")
        c.drawString(55, 710, "Commercial schedule appears on the following page.")
        c.showPage()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(55, 750, "COMMERCIAL OFFER")
    c.setFont("Helvetica", 9)
    labels = [("Vendor", truth["supplier_name"]), ("Offer Ref", truth["quote_number"]), ("Buyer Request", truth["rfq_number"]), ("Denomination", truth["currency"]), ("Valid Through", truth["expiration_date"])]
    for offset, (label, value) in enumerate(labels):
        x = 55 if offset < 3 else 340
        y = 720 - (offset if offset < 3 else offset - 3) * 18
        c.drawString(x, y, f"{label}  /  {value}")
    width_by_field = {"supplier_sku": 90, "description": 150, "quantity": 55, "uom": 45, "unit_price": 70, "stated_line_total": 75}
    widths = [width_by_field[field] for field, _ in order]
    x_positions = [35]
    for width in widths[:-1]:
        x_positions.append(x_positions[-1] + width)
    y = 640
    c.setFont("Helvetica-Bold", 7)
    for x, (_, header) in zip(x_positions, order):
        c.drawString(x, y, header)
    c.setFont("Helvetica", 8)
    for row_number, values in enumerate(rows(truth, order)):
        y -= 38 if index % 4 == 0 else 25
        for x, value in zip(x_positions, values):
            text = str(value)
            c.drawString(x, y, text[:26])
            if len(text) > 26:
                c.drawString(x + 6, y - 10, text[26:52])
        if index % 3 == 0:
            c.line(35, y - 4, 560, y - 4)
    c.setFont("Helvetica", 9)
    c.drawString(55, 500, f"Freight / {truth['shipping_cost']}     Tax / {truth['tax']}     Total / {truth['stated_total']}")
    c.drawString(55, 480, f"Terms / {truth['payment_terms']}     Delivery basis / {truth['shipping_terms']}")
    c.save()


def render_image(pdf_path, image_path, index):
    with tempfile.TemporaryDirectory() as temp:
        prefix = Path(temp) / "page"
        page = "2" if index % 5 == 0 else "1"
        subprocess.run(["pdftoppm", "-f", page, "-l", page, "-singlefile", "-png", "-r", "135", str(pdf_path), str(prefix)], check=True)
        with Image.open(prefix.with_suffix(".png")) as source:
            image = source.convert("RGB")
            if index % 3 == 0:
                image = image.rotate(2.2, expand=True, fillcolor="white")
            if index % 4 == 0:
                image = ImageEnhance.Contrast(image).enhance(0.68)
            if image_path.suffix == ".jpg":
                image.save(image_path, quality=82)
            else:
                image.save(image_path)


def write_spreadsheet(path, truth, index):
    order = HEADER_ORDERS[index % len(HEADER_ORDERS)]
    wb = Workbook()
    ws = wb.active
    ws.title = "Commercial Schedule"
    ws.merge_cells("A1:F1")
    ws["A1"] = f"{truth['supplier_name']} / {truth['quote_number']} / {truth['rfq_number']} / {truth['currency']}"
    for column, (_, header) in enumerate(order, 1):
        ws.cell(4, column, header)
    for row_index, values in enumerate(rows(truth, order), 5):
        for column, value in enumerate(values, 1):
            ws.cell(row_index, column, value)
    ws["A9"] = f"Freight {truth['shipping_cost']} / Tax {truth['tax']} / Total {truth['stated_total']}"
    wb.save(path)


def write_delimited(path, truth, index):
    order = HEADER_ORDERS[index % len(HEADER_ORDERS)]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Vendor", truth["supplier_name"], "Offer Ref", truth["quote_number"], "RFQ", truth["rfq_number"], "Currency", truth["currency"]])
        writer.writerow([header for _, header in order])
        writer.writerows(rows(truth, order))


def write_text(path, truth, index):
    order = HEADER_ORDERS[index % len(HEADER_ORDERS)]
    content = [f"From: quotes@vendor.local", f"Subject: Offer {truth['quote_number']} for {truth['rfq_number']}", f"Vendor / {truth['supplier_name']}", f"Currency / {truth['currency']}", " | ".join(header for _, header in order)]
    content.extend(" | ".join(str(value) for value in row) for row in rows(truth, order))
    content.append(f"Freight {truth['shipping_cost']} | Tax {truth['tax']} | Total {truth['stated_total']} | Net 30")
    path.write_text("\n".join(content), encoding="utf-8")


formats = ["pdf"] * 15 + ["scan.pdf"] * 10 + ["jpg"] * 5 + ["png"] * 5 + ["xlsx"] * 5 + ["csv"] * 5 + ["txt"] * 5
manifest = []
for index, fmt in enumerate(formats, 1):
    truth = data(index)
    stem = f"phase27-holdout-{index:03d}"
    filename = f"{stem}.{fmt}"
    path = DOCS / filename
    if fmt == "pdf":
        draw_pdf(path, truth, index)
    elif fmt == "scan.pdf":
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.pdf"
            image_path = Path(temp) / "scan.png"
            draw_pdf(source, truth, index)
            render_image(source, image_path, index)
            with Image.open(image_path) as image:
                image.convert("RGB").save(path, "PDF", resolution=135)
    elif fmt in {"png", "jpg"}:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.pdf"
            draw_pdf(source, truth, index)
            render_image(source, path, index)
    elif fmt == "xlsx":
        write_spreadsheet(path, truth, index)
    elif fmt == "csv":
        write_delimited(path, truth, index)
    else:
        write_text(path, truth, index)
    truth_path = TRUTH / f"{stem}.json"
    truth_path.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    manifest.append({"id": stem, "path": f"documents/{filename}", "truth": f"ground-truth/{stem}.json", "format": fmt, "origin": "phase27-independent-holdout", "scenarios": ["unseen_layout", "reordered_columns", "multiline" if index % 4 == 0 else "compact"], "attack": False, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
manifest_path = ROOT / "manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
(ROOT / "MANIFEST.sha256").write_text(hashlib.sha256(manifest_path.read_bytes()).hexdigest() + "  manifest.json\n", encoding="utf-8")
print(json.dumps({"documents": len(manifest), "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}))
