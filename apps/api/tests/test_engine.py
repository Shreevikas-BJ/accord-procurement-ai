from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace as NS
import pytest
from sqlalchemy import select
from app.engine import financials, money, percentage, average, comparison, history_analysis
from app.models import RFQ, Quote, QuoteItem, SupplierItemMapping
from app.seed import sid
from app.matching import match_supplier, match_item
from app.schemas import LineItemExtraction


def test_decimal_line_rounding_and_total():
    lines = [NS(quantity=D("3"), unit_price=D("0.335")), NS(quantity=D("5000"), unit_price=D("4.72"))]
    totals, subtotal, total = financials(lines, D("12.49"), D("0"))
    assert totals == [D("1.01"), D("23600.00")]
    assert subtotal == D("23601.01") and total == D("23613.50")


def test_missing_financials_are_not_zero():
    _, subtotal, total = financials([NS(quantity=D(1), unit_price=None)], D(0), D(0))
    assert subtotal is None and total is None
    assert financials([NS(quantity=D(1), unit_price=D(1))], None, D(0))[2] is None


def test_exact_threshold_and_zero_baseline():
    assert percentage(D("18.40"), D("16.73")) < D(".10")
    assert percentage(D("18.403"), D("16.73")) == D(".10")
    assert percentage(D("1"), D("0")) is None
    assert money(D("2.675")) == D("2.68")
    assert average([D("1.10"), D("1.20")]) == D("1.15")


def test_history_filters_future_currency_and_uom():
    rows = [
        NS(id=str(i), date=dt, currency=c, uom=u, unit_price=p, supplier_id="a")
        for i, (dt, c, u, p) in enumerate(
            [
                (date(2026, 8, 1), "USD", "EA", D("10")),
                (date(2026, 9, 10), "USD", "EA", D("1000")),
                (date(2026, 8, 1), "EUR", "EA", D("900")),
                (date(2026, 8, 1), "USD", "BOX", D("800")),
            ]
        )
    ]
    result = history_analysis(rows, D("11"), date(2026, 9, 9), "USD", "EA")
    assert result["average_6m"] == "10.00" and result["change"] == "0.1" and result["sample_count"] == 1


def test_primary_procurement_story(db):
    data = comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))
    q = {x["supplier_name"]: x for x in data["quotes"]}
    assert q["Meridian Components"]["total"] == "118980.00"
    assert q["Atlas Industrial Supply"]["total"] == "127400.00"
    assert q["Nova Supply Group"]["fastest"]
    assert data["recommended_quote_id"] == q["Meridian Components"]["id"]
    assert data["potential_savings"] == "8420.00"
    assert any(a["code"] == "PRICE_INCREASE" for a in q["Atlas Industrial Supply"]["alerts"])
    assert {"MOQ_CONFLICT", "DELIVERY_RISK"} <= {a["code"] for a in q["Vertex Industrial"]["alerts"]}
    assert not q["Vertex Industrial"]["eligible"]
    assert sum(D(x) for x in q["Meridian Components"]["factors"].values()) == D(q["Meridian Components"]["score"])
    assert data == comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("unit_price", None, "MISSING_PRICE"),
        ("lead_time_days", None, "MISSING_LEAD_TIME"),
        ("moq", D(999999), "MOQ_CONFLICT"),
        ("quantity", D(1), "QUANTITY_MISMATCH"),
        ("uom", "BOX", "UOM_MISMATCH"),
        ("item_id", None, "UNMATCHED_ITEM"),
        ("confidence", D(".5"), "LOW_EXTRACTION_CONFIDENCE"),
    ],
)
def test_missing_or_conflicting_line_blocks_ranking(db, field, value, code):
    q = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-3"), Quote.supplier_id == sid("supplier-1")))
    line = db.scalar(select(QuoteItem).where(QuoteItem.quote_id == q.id))
    setattr(line, field, value)
    db.flush()
    data = comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))
    evaluated = next(x for x in data["quotes"] if x["id"] == q.id)
    assert code in {a["code"] for a in evaluated["alerts"]}
    assert not evaluated["eligible"]


def test_currency_mismatch_not_scored_or_recommended(db):
    q = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-3"), Quote.supplier_id == sid("supplier-1")))
    q.currency = "EUR"
    db.flush()
    data = comparison(db, sid("org"), db.get(RFQ, sid("rfq-3")), date(2026, 9, 9))
    row = next(x for x in data["quotes"] if x["id"] == q.id)
    assert row["score"] is None and not row["lowest_cost"] and not row["eligible"]


def test_supplier_alias_and_domain(db):
    assert match_supplier(db, sid("org"), "Atlas Industrial Supply LLC").id == sid("supplier-0")
    assert match_supplier(db, sid("org"), "unrecognized", "sales@meridian.example").id == sid("supplier-1")
    assert match_supplier(db, sid("other-org"), "Atlas Industrial Supply") is None


def test_item_hierarchy_and_human_mapping(db):
    assert match_item(db, sid("org"), sid("supplier-1"), "AX-100")[1] == "Exact SKU"
    assert match_item(db, sid("org"), sid("supplier-1"), "MRC-AX", "AX-100")[1] == "Manufacturer part"
    db.add(
        SupplierItemMapping(
            organization_id=sid("org"),
            supplier_id=sid("supplier-1"),
            supplier_sku="MRC-SPECIAL",
            item_id=sid("item-0"),
            confirmed_by=sid("Buyer"),
        )
    )
    db.flush()
    assert match_item(db, sid("org"), sid("supplier-1"), "MRC-SPECIAL")[0].id == sid("item-0")
    assert match_item(db, sid("org"), sid("supplier-0"), "MRC-SPECIAL")[0] is None
    item, method, candidates = match_item(db, sid("org"), sid("supplier-0"), "unknown", description="Industrial Relay")
    assert item is None and candidates[0]["confidence"] == 1


@pytest.mark.parametrize("value,expected", [("4 weeks", 28), ("4-5 weeks", 35), ("30 days", 30)])
def test_lead_time_normalization(value, expected):
    row = LineItemExtraction(supplier_sku="A", description="Relay", lead_time_days=value)
    assert row.lead_time_days == expected


@pytest.mark.parametrize(
    "field,value", [("quantity", "-1"), ("unit_price", "NaN"), ("unit_price", "-0.01"), ("confidence", "1.1")]
)
def test_invalid_extraction_values_rejected(field, value):
    with pytest.raises(ValueError):
        LineItemExtraction(supplier_sku="A", description="Relay", **{field: value})
