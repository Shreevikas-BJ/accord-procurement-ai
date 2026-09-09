"""Reproducible fictional dataset; safe and idempotent without destructive reset."""

import csv
import hashlib
import json
import os
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from .db import SessionLocal
from .models import (
    Organization,
    User,
    Supplier,
    SupplierContact,
    Item,
    ItemAlias,
    RFQ,
    RFQItem,
    PurchaseHistory,
    ScoringSettings,
    Document,
)
from .auth import hash_password
from .config import DEMO_PATH
from .providers import LocalStorageProvider
from .pipeline import persist_extraction
from .schemas import QuoteExtraction
from .common import audit


def sid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "accord-procurement-demo/" + name))


NAMES = [
    "Atlas Industrial Supply",
    "Meridian Components",
    "Nova Supply Group",
    "Vertex Industrial",
    "Summit Automation",
    "Orion Industrial Components",
]
CATEGORIES = ["Electrical", "HVAC", "Pumps & Valves", "Fasteners", "Automation", "Maintenance", "Bearings", "Motors"]
ANCHOR = date(2026, 9, 9)
PRODUCTS = [
    ("AX-100", "Industrial Relay", "4.48"),
    ("BX-220", "Control Module", "46.58"),
    ("CX-300", "Industrial Switch", "19.80"),
]
QUANTITIES = [5000, 1000, 2500]


def fixture(rfq_num, supplier_index, upload=False):
    prices = [
        ["5.12", "50.80", "20.20"],
        ["4.48", "46.58", "19.80"],
        ["4.55", "47.20", "19.90"],
        ["4.49", "47.40", "19.80"],
    ][supplier_index]
    num = 1000 + rfq_num
    prefix = NAMES[supplier_index].split()[0]
    quote_num = f"{prefix[:3].upper()}-{num}-26" + ("-REV2" if upload else "")
    lead = [36, 24, 18, 60][supplier_index]
    delivery = ANCHOR + timedelta(days=lead)
    values = {
        "supplier_name": NAMES[supplier_index],
        "supplier_email": f"sales@{prefix.lower()}.example",
        "quote_number": quote_num,
        "rfq_number": f"RFQ-{num}",
        "quote_date": str(ANCHOR),
        "expiration_date": "2026-11-30",
        "currency": "USD",
        "payment_terms": "Net 30",
        "shipping_terms": "Delivered to Apex receiving dock",
        "shipping_cost": "500.00",
        "tax": "0.00",
        "confidence": "0.98",
        "notes": "Prices in USD. No purchase commitment. Quote subject to availability.",
    }
    if rfq_num == 4 and supplier_index == 2:
        values["currency"] = "EUR"
    if rfq_num == 2 and supplier_index == 0:
        values["expiration_date"] = "2026-08-31"
    lines = []
    for index, (sku, description, _) in enumerate(PRODUCTS):
        row = {
            "supplier_sku": ("MRC-" + sku if supplier_index == 1 else sku),
            "manufacturer_part_number": sku,
            "description": description,
            "quantity": str(QUANTITIES[index]),
            "uom": "EA",
            "unit_price": prices[index],
            "moq": str(10000 if supplier_index == 3 and index == 0 else 500),
            "lead_time_days": lead,
            "lead_time_min": lead,
            "delivery_date": str(delivery),
            "confidence": "0.98",
            "price_tiers": [],
        }
        if rfq_num == 1 and supplier_index == 2 and index == 1:
            row["lead_time_days"] = None
            row["delivery_date"] = None
        if rfq_num == 4 and supplier_index == 3 and index == 0:
            row["confidence"] = "0.62"
        if rfq_num == 5 and index == 0:
            row["price_tiers"] = [
                {"minimum": "1", "maximum": "499", "unit_price": "6.50"},
                {"minimum": "500", "maximum": None, "unit_price": prices[index]},
            ]
        row["source_references"] = {
            k: {"page": 1, "source_text": f"{k}: {v}", "confidence": row["confidence"]}
            for k, v in row.items()
            if v is not None and k not in ("price_tiers", "confidence")
        }
        lines.append(row)
    values["source_references"] = {
        k: {"page": 1, "source_text": f"{k}: {v}", "confidence": "0.98"} for k, v in values.items()
    }
    values["line_items"] = lines
    return values


def render_fixture(name, data, extension):
    from reportlab.pdfgen.canvas import Canvas
    from openpyxl import Workbook

    lines = [f"{k}: {v}" for k, v in data.items() if k not in ("line_items", "source_references")]
    for row in data["line_items"]:
        lines += ["--- LINE ITEM ---"] + [
            f"{k}: {v}" for k, v in row.items() if k not in ("source_references", "price_tiers")
        ]
    target = DEMO_PATH / "quotes" / (name + extension)
    if extension == ".pdf":
        canvas = Canvas(str(target), pagesize=(700, 1000), invariant=True)
        canvas.setTitle(name)
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawString(40, 960, data["supplier_name"].upper())
        canvas.setFont("Helvetica", 9)
        y = 930
        for line in lines:
            canvas.drawString(40, y, line[:130])
            y -= 13
        canvas.save()
    elif extension == ".xlsx":
        book = Workbook()
        sheet = book.active
        sheet.title = "Quotation"
        for line in lines:
            sheet.append([line])
        sheet.column_dimensions["A"].width = 100
        book.save(target)
    elif extension == ".csv":
        with target.open("w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            writer.writerows([[line] for line in lines])
    else:
        target.write_text("\n".join(lines), encoding="utf-8")
    return target


def generate_fixtures():
    for folder in ("quotes", "ground-truth", "imports"):
        (DEMO_PATH / folder).mkdir(parents=True, exist_ok=True)
    if (DEMO_PATH / "manifest.json").exists():
        return
    manifest, index = {}, []
    for r in range(1, 6):
        for s in range(4):
            data = fixture(r, s)
            name = f"{NAMES[s].split()[0]}_RFQ{1000 + r}"
            extension = [".pdf", ".xlsx", ".csv", ".pdf"][s]
            target = render_fixture(name, data, extension)
            ground = name + ".json"
            (DEMO_PATH / "ground-truth" / ground).write_text(json.dumps(data, indent=2), encoding="utf-8")
            manifest[hashlib.sha256(target.read_bytes()).hexdigest()] = ground
            index.append({"name": target.name, "ground_truth": ground, "rfq": r})
    for s, extension in enumerate([".pdf", ".xlsx", ".csv"]):
        data = fixture(3, s, upload=True)
        name = f"Upload_{NAMES[s].split()[0]}_RFQ1003"
        target = render_fixture(name, data, extension)
        ground = name + ".json"
        (DEMO_PATH / "ground-truth" / ground).write_text(json.dumps(data, indent=2))
        manifest[hashlib.sha256(target.read_bytes()).hexdigest()] = ground
    # A real raster sample exercises Tesseract; fixture extraction remains deterministic.
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    data = fixture(4, 3, upload=True)
    target = DEMO_PATH / "quotes" / "Scanned_Vertex_RFQ1004.png"
    image = Image.new("RGB", (1600, 2000), "white")
    draw = ImageDraw.Draw(image)
    text = "\n".join(f"{k}: {v}" for k, v in data.items() if k not in ("source_references", "line_items"))
    text += "\n\n" + "\n".join(
        f"{x['supplier_sku']} Qty {x['quantity']} Unit price {x['unit_price']} MOQ {x['moq']}"
        for x in data["line_items"]
    )
    draw.multiline_text((60, 80), text, font=ImageFont.load_default(size=28), fill="black", spacing=18)
    image.save(target)
    ground = "Scanned_Vertex_RFQ1004.json"
    (DEMO_PATH / "ground-truth" / ground).write_text(json.dumps(data, indent=2))
    manifest[hashlib.sha256(target.read_bytes()).hexdigest()] = ground
    pdf_target = target.with_suffix(".pdf")
    canvas = Canvas(str(pdf_target), invariant=True)
    canvas.drawImage(ImageReader(image), 0, 0, width=595, height=842)
    canvas.save()
    manifest[hashlib.sha256(pdf_target.read_bytes()).hexdigest()] = ground
    (DEMO_PATH / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (DEMO_PATH / "seed-index.json").write_text(json.dumps(index, indent=2))
    with (DEMO_PATH / "imports" / "purchase-history.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "po_number",
                "date",
                "supplier",
                "sku",
                "quantity",
                "unit_price",
                "currency",
                "uom",
                "lead_time_days",
                "expected_delivery",
                "actual_delivery",
            ]
        )
        writer.writerow(
            [
                "PO-IMPORT-001",
                "2026-08-01",
                NAMES[1],
                "AX-100",
                5000,
                "4.48",
                "USD",
                "EA",
                24,
                "2026-08-25",
                "2026-08-24",
            ]
        )


def seed():
    generate_fixtures()
    with SessionLocal() as db:
        if db.get(Organization, sid("org")):
            print("Demo organization already seeded; no changes made.")
            return
        org = sid("org")
        db.add(Organization(id=org, name="Apex Industrial Manufacturing", currency="USD"))
        db.add(Organization(id=sid("other-org"), name="Isolated Demo Organization", currency="USD"))
        db.flush()
        for role in ("Admin", "Buyer", "Viewer"):
            db.add(
                User(
                    id=sid(role),
                    organization_id=org,
                    email=role.lower() + "@apex.example",
                    name={"Admin": "Alex Morgan", "Buyer": "Jordan Lee", "Viewer": "Casey Rivera"}[role],
                    role=role,
                    password_hash=hash_password("Demo2026!accord"),
                )
            )
        db.add(
            User(
                id=sid("other-user"),
                organization_id=sid("other-org"),
                email="viewer@isolated.example",
                name="Isolated Viewer",
                role="Viewer",
                password_hash=hash_password("Demo2026!accord"),
            )
        )
        db.add(
            ScoringSettings(
                organization_id=org, anomaly_threshold=Decimal(os.getenv("PRICE_ANOMALY_THRESHOLD", "0.10"))
            )
        )
        db.add(ScoringSettings(organization_id=sid("other-org")))
        db.flush()
        names = NAMES + [
            f"{['Cobalt', 'Northstar', 'Pinnacle', 'Evergreen', 'Stonebridge', 'Cedar', 'Horizon', 'Silverline'][i % 8]} {['Mechanical', 'Controls', 'Industrial', 'Engineering', 'Components', 'Supply'][i // 8]}"
            for i in range(44)
        ]
        for i, name in enumerate(names):
            supplier_id = sid(f"supplier-{i}")
            prefix = name.split()[0].lower()
            db.add(
                Supplier(
                    id=supplier_id,
                    organization_id=org,
                    name=name,
                    aliases=[name + " LLC", prefix.title() + " Industrial"] if i == 0 else [name + " Ltd"],
                    category=CATEGORIES[0 if i < 4 else i % 8],
                    email_domain=prefix + ".example",
                    preferred_supplier=i == 1,
                )
            )
        db.flush()
        for i, name in enumerate(names):
            db.add(
                SupplierContact(
                    organization_id=org,
                    supplier_id=sid(f"supplier-{i}"),
                    name="Sales Team",
                    email=f"sales@{name.split()[0].lower()}.example",
                )
            )
        for i in range(250):
            sku, description, _ = (
                PRODUCTS[i]
                if i < 3
                else (
                    f"COMP-{i + 1000}",
                    f"{CATEGORIES[i % 8]} {['Assembly', 'Module', 'Connector', 'Kit', 'Adapter'][i % 5]} {i + 1000}",
                    "12.50",
                )
            )
            db.add(
                Item(
                    id=sid(f"item-{i}"),
                    organization_id=org,
                    sku=sku,
                    manufacturer_part_number=sku,
                    description=description,
                    category=CATEGORIES[0 if i < 3 else i % 8],
                    uom="EA",
                    preferred_supplier_id=sid("supplier-1") if i < 3 else None,
                )
            )
        db.flush()
        for i in range(3):
            db.add(ItemAlias(organization_id=org, item_id=sid(f"item-{i}"), alias=PRODUCTS[i][0].replace("-", "")))
        rng = random.Random(2026)
        for i in range(2000):
            item_index = i % 3 if i < 240 else rng.randrange(250)
            supplier_index = i % 4 if i < 240 else rng.randrange(50)
            dt = ANCHOR - timedelta(days=1 + i % 180)
            lead = [36, 24, 18, 41][supplier_index % 4]
            expected = dt + timedelta(days=lead)
            actual = expected + timedelta(
                days=(3 if supplier_index == 0 and i % 8 == 0 else 2 if supplier_index == 2 and i % 8 == 2 else 0)
            )
            price = Decimal(PRODUCTS[item_index][2]) if item_index < 3 else Decimal(str(rng.randint(250, 20000))) / 100
            db.add(
                PurchaseHistory(
                    id=sid(f"purchase-{i}"),
                    organization_id=org,
                    po_number=f"PO-{260000 + i}",
                    date=dt,
                    supplier_id=sid(f"supplier-{supplier_index}"),
                    item_id=sid(f"item-{item_index}"),
                    quantity=QUANTITIES[item_index] if item_index < 3 else rng.randrange(10, 500),
                    unit_price=price,
                    currency="USD",
                    uom="EA",
                    lead_time_days=lead,
                    expected_delivery=expected,
                    actual_delivery=actual if actual <= ANCHOR else None,
                )
            )
        titles = [
            "Plant Maintenance Components",
            "Automation Line Upgrade",
            "Industrial Electrical Components",
            "Control Cabinet Refurbishment",
            "Quarterly Production Replenishment",
        ]
        for r in range(1, 6):
            db.add(
                RFQ(
                    id=sid(f"rfq-{r}"),
                    organization_id=org,
                    number=f"RFQ-{1000 + r}",
                    title=titles[r - 1],
                    description="Competitive sourcing for Apex production facilities. Evaluate full scope, delivery, and historical pricing before approval.",
                    required_delivery=date(2026, 10, 30),
                    created_by=sid("Buyer"),
                    supplier_count=4 if r == 3 else 5,
                    status="Quotes Received",
                )
            )
        db.flush()
        for r in range(1, 6):
            for i in range(3):
                db.add(
                    RFQItem(
                        organization_id=org, rfq_id=sid(f"rfq-{r}"), item_id=sid(f"item-{i}"), quantity=QUANTITIES[i]
                    )
                )
        db.flush()
        for entry in json.loads((DEMO_PATH / "seed-index.json").read_text()):
            path = DEMO_PATH / "quotes" / entry["name"]
            content = path.read_bytes()
            id = sid(entry["name"])
            key = LocalStorageProvider().save(org, id + path.suffix, content)
            mime = {
                ".pdf": "application/pdf",
                ".csv": "text/csv",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }[path.suffix]
            payload = QuoteExtraction.model_validate_json(
                (DEMO_PATH / "ground-truth" / entry["ground_truth"]).read_text()
            )
            raw = (
                "\n".join(e.source_text for e in payload.source_references.values())
                + "\n\n"
                + "\n\n".join(
                    "\n".join(e.source_text for e in line.source_references.values()) for line in payload.line_items
                )
            )
            doc = Document(
                id=id,
                organization_id=org,
                filename=entry["name"],
                mime_type=mime,
                storage_key=key,
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                raw_text=raw,
                rfq_id=sid(f"rfq-{entry['rfq']}"),
                uploaded_by=sid("Buyer"),
                created_at=datetime.now(timezone.utc) - timedelta(seconds=2),
            )
            db.add(doc)
            db.flush()
            audit(db, org, sid("Buyer"), "QUOTE_UPLOADED", "document", id, new={"filename": entry["name"]})
            persist_extraction(db, doc, payload, "demo")
        db.commit()
        print("Seeded Apex: 50 suppliers, 250 items, 2,000 purchases, 5 RFQs, 20 quotes, 4 users.")


if __name__ == "__main__":
    seed()
