"""Fifteen distinct stress cases: source date formats, precision, long documents,
multi-sheet offers, ambiguous dates, irrelevant tables and split deliveries."""

import csv
import hashlib
import json
import shutil
import subprocess
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path

from build_extraction_corpus import dump, make_case, pdf, rows_for
from openpyxl import Workbook
from PIL import Image, ImageEnhance
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark-data"
CASES = [
    ("email_written_dates", "txt"),
    ("european_dates_precision", "pdf"),
    ("alternate_column_labels", "csv"),
    ("multi_sheet_offer", "xlsx"),
    ("scan_written_dates", "scan.pdf"),
    ("low_contrast_box_quote", "jpg"),
    ("twenty_page_commercial_selection", "pdf"),
    ("ambiguous_delivery_date", "txt"),
    ("six_decimal_unit_price", "csv"),
    ("uncached_formula_total", "xlsx"),
    ("wrapped_description", "pdf"),
    ("stock_and_offer_tables", "png"),
    ("previous_offer_distractor", "txt"),
    ("twelve_page_scanned_selection", "scan.pdf"),
    ("same_sku_split_deliveries", "txt"),
]


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    for index, (scenario, kind) in enumerate(CASES, 61):
        identifier = f"synthetic-{index:03d}-{scenario}"
        if any(e["id"] == identifier for e in manifest):
            continue
        q, _ = make_case(0)
        q.update(
            supplier_name=[
                "Beacon Precision Works",
                "Riverbend Hydraulics",
                "Clearwater Cable Co",
                "Mesa Mechanical",
                "Elm Circuit Supply",
            ][index % 5],
            quote_number=f"BP/{index}/26",
            rfq_number=f"REQ-{8200 + index}",
            currency=["USD", "EUR", "GBP"][index % 3],
        )
        line = q["line_items"][0]
        line.update(
            supplier_sku=f"BP/{index}-X.02",
            description="Ceramic terminal block",
            quantity=str(30 + index),
            unit_price=str(D(index) / 10),
            moq="10",
            lead_time_days=28,
            delivery_date="2026-10-15",
        )
        if scenario == "european_dates_precision":
            line.update(quantity="12.375", unit_price="0.0042", uom="KG")
        if scenario == "six_decimal_unit_price":
            line.update(quantity="10000", unit_price="0.000042")
        if scenario == "low_contrast_box_quote":
            line.update(uom="BOX", quantity="12", unit_price="87.50")
        if scenario == "same_sku_split_deliveries":
            other = deepcopy(line)
            other.update(
                quantity="50",
                unit_price="7.25",
                delivery_date="2026-10-29",
                lead_time_days=42,
            )
            q["line_items"].append(other)
        for record in q["line_items"]:
            record["stated_line_total"] = str(
                D(record["quantity"]) * D(record["unit_price"])
            )
        q["stated_subtotal"] = str(
            sum(D(record["stated_line_total"]) for record in q["line_items"])
        )
        q["stated_total"] = str(
            D(q["stated_subtotal"]) + D(q["shipping_cost"]) + D(q["tax"])
        )
        rows = rows_for(q, "standard_table", 2)
        if scenario in ("email_written_dates", "scan_written_dates"):
            rows = [
                [
                    str(cell)
                    .replace("2026-09-01", "September 1, 2026")
                    .replace("2026-10-15", "October 15, 2026")
                    .replace("2026-11-30", "November 30, 2026")
                    for cell in row
                ]
                for row in rows
            ]
        if scenario == "european_dates_precision":
            rows = [
                [
                    str(cell)
                    .replace("2026-09-01", "01.09.2026")
                    .replace("2026-10-15", "15.10.2026")
                    .replace("2026-11-30", "30.11.2026")
                    for cell in row
                ]
                for row in rows
            ]
            rows.insert(1, ["Date convention", "DD.MM.YYYY"])
        if scenario == "ambiguous_delivery_date":
            rows = [
                [str(cell).replace("2026-10-15", "10/11/2026") for cell in row]
                for row in rows
            ]
            rows.append(
                [
                    "Delivery date convention",
                    "Not specified; ask supplier to clarify month/day order",
                ]
            )
            line["delivery_date"] = None
        if scenario == "alternate_column_labels":
            substitutions = {
                "SKU": "Vendor part no.",
                "Qty": "Order quantity",
                "Unit price": "Price per unit",
                "MOQ": "Minimum order quantity",
            }
            rows = [[substitutions.get(cell, cell) for cell in row] for row in rows]
        if scenario == "previous_offer_distractor":
            rows.insert(
                1,
                [
                    "Withdrawn previous offer, not current",
                    "BP/74-X.02, quantity 250, unit price 99.00",
                ],
            )
        if scenario == "stock_and_offer_tables":
            rows[1:1] = [
                ["WAREHOUSE STOCK REPORT - NOT AN OFFER"],
                ["Part", "Stock on hand", "Last year's price"],
                [line["supplier_sku"], "500000", "0.01"],
                ["CURRENT SUPPLIER OFFER BELOW"],
            ]
        if scenario == "wrapped_description":
            q["line_items"][0]["description"] = (
                "Ceramic terminal block, rated for elevated temperature"
            )
            position = next(
                i
                for i, row in enumerate(rows)
                if row and row[0] == line["supplier_sku"]
            )
            rows.insert(
                position + 1,
                ["Description continued", "rated for elevated temperature"],
            )
        destination = OUT / "documents" / f"{identifier}.{kind}"
        temporary = OUT / "previews" / f"{identifier}.pdf"
        if kind == "txt":
            destination.write_text(
                "From: quotations@fictional.example\nTo: buyer@evaluation.example\nSubject: Current commercial quotation\n\n"
                + "\n".join(" | ".join(map(str, row)) for row in rows),
                encoding="utf-8",
            )
        elif kind == "csv":
            with destination.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerows(rows)
        elif kind == "xlsx":
            workbook = Workbook()
            sheet = workbook.active
            if scenario == "multi_sheet_offer":
                sheet.title = "Buyer instructions"
                sheet.append(["BUYER", "Accord Evaluation Lab"])
                sheet.append(
                    ["Reference only", "See Commercial Offer tab for supplier pricing"]
                )
                sheet = workbook.create_sheet("Commercial Offer")
            for row in rows:
                sheet.append(row)
            if scenario == "uncached_formula_total":
                for row in sheet:
                    if row[0].value in ("Subtotal", "Grand total"):
                        row[1].value = "=SUM(1,2)"
                q["stated_subtotal"] = q["stated_total"] = None
            workbook.save(destination)
        else:
            pdf(temporary, rows, 2)
            if scenario in (
                "twenty_page_commercial_selection",
                "twelve_page_scanned_selection",
            ):
                count, commercial = (20, 17) if kind == "pdf" else (12, 9)
                generic = temporary.with_name(identifier + "-terms.pdf")
                c = canvas.Canvas(str(generic), pagesize=(1000, 780))
                c.setFont("Helvetica", 12)
                c.drawString(
                    40, 730, q["supplier_name"] + " - Technical materials manual"
                )
                for number in range(15):
                    c.drawString(
                        40,
                        690 - number * 25,
                        "Material handling and general maintenance information. No commercial offer on this page.",
                    )
                c.save()
                writer = PdfWriter()
                for page_number in range(1, count + 1):
                    writer.add_page(
                        PdfReader(
                            temporary if page_number == commercial else generic
                        ).pages[0]
                    )
                long_path = temporary.with_name(identifier + "-long.pdf")
                writer.write(long_path)
                temporary = long_path
            if kind == "pdf":
                shutil.copyfile(temporary, destination)
            else:
                prefix = OUT / "previews" / (identifier + "-raster")
                subprocess.run(
                    [
                        "pdftoppm",
                        "-scale-to",
                        "1600",
                        "-png",
                        str(temporary),
                        str(prefix),
                    ],
                    check=True,
                    capture_output=True,
                )
                pages = sorted(prefix.parent.glob(prefix.name + "-*.png"))
                if kind == "scan.pdf":
                    c = canvas.Canvas(str(destination), pagesize=(1000, 780))
                    for page in pages:
                        c.drawImage(
                            ImageReader(str(page)), 0, 0, width=1000, height=780
                        )
                        c.showPage()
                    c.save()
                else:
                    image = Image.open(pages[0]).convert("RGB")
                    if kind == "jpg":
                        image = ImageEnhance.Contrast(image).enhance(0.65)
                    image.save(destination, quality=70)
        dump(OUT / "ground-truth" / f"{identifier}.json", q)
        manifest.append(
            {
                "id": identifier,
                "path": str(destination.relative_to(OUT)),
                "truth": f"ground-truth/{identifier}.json",
                "format": kind,
                "origin": "fictional-generated",
                "scenarios": [scenario],
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            }
        )
    dump(OUT / "manifest.json", manifest)
    print(json.dumps({"documents": len(manifest), "new_cases": len(CASES)}))


if __name__ == "__main__":
    main()
