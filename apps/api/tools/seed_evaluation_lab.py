"""Create a separate tenant/catalog for five opt-in local UI smoke documents."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, func
from app.auth import hash_password
from app.db import SessionLocal
from app.models import Organization, User, Supplier, Item, RFQ, RFQItem, ScoringSettings, PurchaseHistory, Document
from app.seed import sid

CASES = [
    "synthetic-001-standard_table",
    "synthetic-002-supplier_sku_and_mpn",
    "synthetic-003-comma_thousands",
    "synthetic-005-lead_time_range",
    "synthetic-006-weeks",
]


def main(cases=None, namespace="evaluation", name="Accord Evaluation Lab", email="buyer@evaluation.example"):
    cases = cases or CASES
    corpus = Path("/app/benchmark-data")
    org_id = sid(namespace + "-lab")
    user_id = sid(namespace + "-buyer")
    with SessionLocal() as db:
        apex_before = {
            "documents": db.scalar(
                select(func.count()).select_from(Document).where(Document.organization_id == sid("org"))
            ),
            "history": db.scalar(
                select(func.count()).select_from(PurchaseHistory).where(PurchaseHistory.organization_id == sid("org"))
            ),
        }
        if not db.get(Organization, org_id):
            db.add(Organization(id=org_id, name=name, currency="USD"))
            db.flush()
            db.add(
                User(
                    id=user_id,
                    organization_id=org_id,
                    email=email,
                    name="Evaluation Buyer",
                    password_hash=hash_password("Demo2026!accord"),
                    role="Buyer",
                )
            )
            db.add(ScoringSettings(organization_id=org_id))
            db.flush()
        for case in cases:
            case_root = corpus / "reliability" if case.startswith("reliability-") else corpus
            q = json.loads((case_root / "ground-truth" / f"{case}.json").read_text())
            supplier_id = sid(namespace + "-supplier-" + q["supplier_name"])
            if not db.get(Supplier, supplier_id):
                db.add(
                    Supplier(
                        id=supplier_id,
                        organization_id=org_id,
                        name=q["supplier_name"],
                        category="Evaluation",
                        email_domain="fictional.example",
                        currency=q["currency"],
                    )
                )
                db.flush()
            rfq_id = sid(namespace + "-rfq-" + q["rfq_number"])
            if db.get(RFQ, rfq_id):
                continue
            db.add(
                RFQ(
                    id=rfq_id,
                    organization_id=org_id,
                    number=q["rfq_number"],
                    title="Local AI evaluation: " + case,
                    currency=q["currency"],
                    required_delivery=date(2026, 11, 30),
                    supplier_count=1,
                    created_by=user_id,
                )
            )
            db.flush()
            for line in q["line_items"]:
                item_id = sid(namespace + "-item-" + line["supplier_sku"])
                db.add(
                    Item(
                        id=item_id,
                        organization_id=org_id,
                        sku=line["supplier_sku"],
                        manufacturer_part_number=line.get("manufacturer_part_number") or line["supplier_sku"],
                        description=line["description"],
                        category="Evaluation",
                        uom=line["uom"],
                    )
                )
                db.flush()
                db.add(
                    # This is the buyer's RFQ demand, never extraction evidence.
                    RFQItem(
                        organization_id=org_id,
                        rfq_id=rfq_id,
                        item_id=item_id,
                        quantity=Decimal(line["quantity"] or "100"),
                    )
                )
        db.commit()
        print(
            json.dumps(
                {
                    "organization": name,
                    "organization_id": org_id,
                    "cases": cases,
                    "apex_before": apex_before,
                    "evaluation_purchase_history": db.scalar(
                        select(func.count())
                        .select_from(PurchaseHistory)
                        .where(PurchaseHistory.organization_id == org_id)
                    ),
                }
            )
        )


if __name__ == "__main__":
    main()
