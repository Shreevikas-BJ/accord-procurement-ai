from datetime import date
from decimal import Decimal
from sqlalchemy import select
from app.models import Quote, QuoteItem, RFQ
from app.engine import comparison
from app.seed import sid


def test_incomplete_fast_offer_never_exceeds_score_bounds(db):
    quote = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-3"), Quote.supplier_id == sid("supplier-1")))
    lines = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote.id)).all()
    for line in lines:
        line.lead_time_days = 0
    lines[0].quantity = 1
    db.flush()
    result = comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))
    for evaluated in result["quotes"]:
        assert 0 <= Decimal(evaluated["score"]) <= 100
    assert result["recommended_quote_id"] != quote.id


def test_free_complete_offer_has_full_price_score(db):
    quote = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-3"), Quote.supplier_id == sid("supplier-1")))
    quote.shipping_cost = 0
    for line in db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote.id)):
        line.unit_price = 0
    db.flush()
    result = comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))
    evaluated = next(q for q in result["quotes"] if q["id"] == quote.id)
    assert evaluated["factors"]["price"] == "50.00"
    assert result["recommended_quote_id"] == quote.id
