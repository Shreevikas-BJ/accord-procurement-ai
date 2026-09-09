from datetime import date
from types import SimpleNamespace
from sqlalchemy import select
from app.models import Quote, QuoteItem, RFQ, Document
from app.seed import sid
from app.engine import comparison
from app.pipeline import job_failed
from app.config import DEMO_PATH
from app.schemas import PriceTier
import pytest


def test_tier_price_mismatch_blocks_recommendation(db):
    q = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-5"), Quote.supplier_id == sid("supplier-1")))
    line = db.scalar(select(QuoteItem).where(QuoteItem.quote_id == q.id, QuoteItem.item_id == sid("item-0")))
    line.unit_price = 1
    db.flush()
    data = comparison(db, sid("org"), db.get(RFQ, sid("rfq-5")), date(2026, 9, 9))
    evaluated = next(row for row in data["quotes"] if row["id"] == q.id)
    assert not evaluated["eligible"]
    assert any(a["code"] == "TIER_PRICE_MISMATCH" for a in evaluated["alerts"])


def test_tier_range_rejected():
    with pytest.raises(ValueError):
        PriceTier(minimum=100, maximum=10, unit_price=5)


def test_buyer_can_create_tenant_scoped_item(buyer):
    response = buyer.post(
        "/items",
        json={
            "sku": "NEW-RELAY",
            "manufacturer_part_number": "R-123",
            "description": "New verified relay",
            "category": "Electrical",
            "uom": "EA",
        },
    )
    assert response.status_code == 201
    assert response.json()["organization_id"] == sid("org")
    assert buyer.get("/items?search=NEW-RELAY").json()["total"] == 1


def test_job_timeout_is_actionable(db):
    doc = db.scalar(select(Document).where(Document.organization_id == sid("org")))
    doc.status = "Processing"
    db.commit()
    job_failed(SimpleNamespace(args=(doc.id, sid("org"))), None, TimeoutError, None, None)
    db.refresh(doc)
    assert doc.status == "Error" and doc.stage == "Worker failed"


def test_import_history_admin_and_atomicity(buyer):
    content = (DEMO_PATH / "imports" / "purchase-history.csv").read_bytes()
    assert (
        buyer.post("/purchase-history/import", files={"file": ("history.csv", content, "text/csv")}).status_code == 403
    )
    buyer.post("/auth/login", json={"email": "admin@apex.example", "password": "Demo2026!accord"})
    assert (
        buyer.post("/purchase-history/import", files={"file": ("history.csv", content, "text/csv")}).status_code == 201
    )
    assert buyer.get("/purchase-history?search=Meridian").json()["total"] > 0
    assert buyer.get("/purchase-history?search=AX-100").json()["total"] > 0
    assert (
        buyer.post("/purchase-history/import", files={"file": ("history.csv", content, "text/csv")}).status_code == 409
    )


def test_human_review_can_resolve_low_extraction_confidence(db):
    q = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-3"), Quote.supplier_id == sid("supplier-1")))
    q.confidence = 0.2
    db.flush()
    before = comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))
    assert not next(row for row in before["quotes"] if row["id"] == q.id)["eligible"]
    q.review_status = "Reviewed"
    db.flush()
    after = comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))
    assert next(row for row in after["quotes"] if row["id"] == q.id)["eligible"]
