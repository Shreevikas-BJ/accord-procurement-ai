"""All arithmetic and supplier decisions are deterministic and use Decimal."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, delete
from .models import Quote, QuoteItem, RFQItem, Item, PurchaseHistory, Supplier, ScoringSettings, Alert
from .common import serialize, audit

D = Decimal


def money(value):
    return D(value).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def percentage(current, baseline):
    return (D(current) - D(baseline)) / D(baseline) if baseline else None


def average(values):
    return sum(values, D(0)) / len(values) if values else None


def financials(lines, shipping, tax):
    totals = [
        money(x.quantity * x.unit_price) if x.quantity is not None and x.unit_price is not None else None for x in lines
    ]
    subtotal = sum((x for x in totals if x is not None), D(0))
    complete = all(x is not None for x in totals) and shipping is not None and tax is not None
    return totals, money(subtotal), money(subtotal + (shipping or D(0)) + (tax or D(0))) if complete else None


def history_analysis(rows, current, as_of, currency, uom, supplier_id=None):
    valid = sorted(
        [
            h
            for h in rows
            if h.date <= as_of
            and h.currency == currency
            and h.uom == uom
            and (supplier_id is None or h.supplier_id == supplier_id)
        ],
        key=lambda h: (h.date, h.id),
        reverse=True,
    )
    six = [h.unit_price for h in valid if h.date >= as_of - timedelta(days=183)]
    three = [h.unit_price for h in valid if h.date >= as_of - timedelta(days=92)]
    avg = average(six)
    return {
        "last_price": str(valid[0].unit_price) if valid else None,
        "last_date": str(valid[0].date) if valid else None,
        "average_3m": str(money(average(three))) if three else None,
        "average_6m": str(money(avg)) if avg is not None else None,
        "change": str(percentage(current, avg)) if current is not None and avg else None,
        "sample_count": len(six),
    }


def comparison(db, org, rfq, today=None):
    today = today or date.today()
    settings = db.scalar(select(ScoringSettings).where(ScoringSettings.organization_id == org))
    weights = {
        "price": settings.price_weight,
        "lead_time": settings.lead_time_weight,
        "reliability": settings.reliability_weight,
        "fit": settings.fit_weight,
    }
    quotes = db.scalars(
        select(Quote).where(Quote.organization_id == org, Quote.rfq_id == rfq.id).order_by(Quote.created_at, Quote.id)
    ).all()
    quote_ids = [q.id for q in quotes]
    all_lines = db.scalars(
        select(QuoteItem).where(QuoteItem.organization_id == org, QuoteItem.quote_id.in_(quote_ids))
    ).all()
    requirements = db.scalars(select(RFQItem).where(RFQItem.organization_id == org, RFQItem.rfq_id == rfq.id)).all()
    items = {
        i.id: i
        for i in db.scalars(
            select(Item).where(Item.organization_id == org, Item.id.in_([r.item_id for r in requirements]))
        )
    }
    suppliers = {
        s.id: s
        for s in db.scalars(
            select(Supplier).where(
                Supplier.organization_id == org, Supplier.id.in_([q.supplier_id for q in quotes if q.supplier_id])
            )
        )
    }
    history = db.scalars(
        select(PurchaseHistory).where(
            PurchaseHistory.organization_id == org,
            PurchaseHistory.date <= today,
            PurchaseHistory.item_id.in_(list(items)),
        )
    ).all()
    results = []
    for quote in quotes:
        lines = [x for x in all_lines if x.quote_id == quote.id]
        totals, subtotal, total = financials(lines, quote.shipping_cost, quote.tax)
        alerts = []

        def flag(code, message, severity="warning"):
            alerts.append({"code": code, "message": message, "severity": severity})

        if not quote.supplier_id:
            flag("UNMATCHED_SUPPLIER", "Confirm supplier identity.", "blocking")
        if quote.currency != rfq.currency:
            flag(
                "CURRENCY_MISMATCH",
                f"{quote.currency} quote cannot be compared with {rfq.currency}. No FX conversion applied.",
                "blocking",
            )
        if quote.expiration_date and quote.expiration_date < today:
            flag("QUOTE_EXPIRED", f"Quotation expired on {quote.expiration_date}.", "blocking")
        if not quote.expiration_date:
            flag("MISSING_EXPIRATION", "Quote validity needs confirmation.", "blocking")
        if quote.confidence < D(".8") and quote.review_status != "Reviewed":
            flag("LOW_EXTRACTION_CONFIDENCE", "Quote extraction needs human verification.", "blocking")
        if quote.shipping_cost is None or quote.tax is None:
            flag("MISSING_COST", "Shipping or tax is unknown; evaluated total is unavailable.", "blocking")
        if sum(q.supplier_id == quote.supplier_id and q.quote_number == quote.quote_number for q in quotes) > 1:
            flag("DUPLICATE_QUOTE", "Supplier quote number appears more than once.", "blocking")
        line_results = []
        latest = None
        leads = []
        for line, line_total in zip(lines, totals):
            item = items.get(line.item_id)
            req = next((r for r in requirements if r.item_id == line.item_id), None)
            label = item.sku if item else line.supplier_sku
            if not item:
                flag("UNMATCHED_ITEM", f"{label}: confirm internal item mapping.", "blocking")
            if line.unit_price is None:
                flag("MISSING_PRICE", f"{label}: unit price is missing.", "blocking")
            if line.quantity is None or (req and line.quantity != req.quantity):
                flag("QUANTITY_MISMATCH", f"{label}: quoted quantity differs from requirement.", "blocking")
            if not line.uom or (item and line.uom != item.uom):
                flag("UOM_MISMATCH", f"{label}: unit of measure requires review.", "blocking")
            if line.moq is None:
                flag("MISSING_MOQ", f"{label}: minimum order quantity is unknown.", "blocking")
            elif req and line.moq > req.quantity:
                flag("MOQ_CONFLICT", f"{label}: MOQ {line.moq:,.0f} exceeds required {req.quantity:,.0f}.", "blocking")
            delivery = line.delivery_date
            if line.lead_time_days is None:
                flag("MISSING_LEAD_TIME", f"{label}: lead time is missing.", "blocking")
            else:
                leads.append(line.lead_time_days)
                # Lead times start when an order could be placed, never the stale quote date.
                delivery = delivery or today + timedelta(days=line.lead_time_days)
            if delivery:
                latest = max(latest, delivery) if latest else delivery
                if delivery > rfq.required_delivery:
                    flag(
                        "DELIVERY_RISK",
                        f"{label}: delivery {delivery} misses target by {(delivery - rfq.required_delivery).days} days.",
                        "blocking",
                    )
            if quote.review_status != "Reviewed" and (
                line.confidence < D(".8")
                or any(D(str(e.get("confidence", 0))) < D(".8") for e in line.source_references.values())
            ):
                flag("LOW_EXTRACTION_CONFIDENCE", f"{label}: verify low-confidence fields.", "blocking")
            if line.price_tiers and line.quantity is not None:
                applicable = [
                    t
                    for t in line.price_tiers
                    if D(t["minimum"]) <= line.quantity and (t["maximum"] is None or line.quantity <= D(t["maximum"]))
                ]
                if len(applicable) != 1 or line.unit_price != D(applicable[0]["unit_price"]):
                    flag(
                        "TIER_PRICE_MISMATCH",
                        f"{label}: selected unit price does not match exactly one quantity tier.",
                        "blocking",
                    )
            if (
                line.stated_line_total is not None
                and line_total is not None
                and money(line.stated_line_total) != line_total
            ):
                flag("TOTAL_MISMATCH", f"{label}: stated total differs from calculated total.", "blocking")
            ha = history_analysis(
                [h for h in history if h.item_id == line.item_id],
                line.unit_price,
                quote.quote_date or today,
                quote.currency,
                line.uom,
            )
            if ha["change"] is not None and D(ha["change"]) >= settings.anomaly_threshold:
                flag("PRICE_INCREASE", f"{label}: +{D(ha['change']) * 100:.1f}% vs six-month average.")
            line_results.append(
                {
                    **serialize(line),
                    "sku": item.sku if item else None,
                    "line_total": str(line_total) if line_total is not None else None,
                    "history": ha,
                    "expected_delivery": str(delivery) if delivery else None,
                }
            )
        for req in requirements:
            if sum(x.item_id == req.item_id for x in lines) != 1:
                flag("INCOMPLETE_SCOPE", f"{items[req.item_id].sku}: require exactly one quoted line.", "blocking")
        if quote.stated_subtotal is not None and money(quote.stated_subtotal) != subtotal:
            flag("TOTAL_MISMATCH", "Stated subtotal differs from calculated subtotal.", "blocking")
        if quote.stated_total is not None and total is not None and money(quote.stated_total) != total:
            flag("TOTAL_MISMATCH", "Stated total differs from calculated total.", "blocking")
        supplier_history = [h for h in history if h.supplier_id == quote.supplier_id and h.actual_delivery is not None]
        reliability = (
            D(sum(h.actual_delivery <= h.expected_delivery for h in supplier_history)) / len(supplier_history)
            if supplier_history
            else D(".5")
        )
        eligible = not any(a["severity"] == "blocking" for a in alerts) and total is not None and bool(lines)
        results.append(
            {
                **serialize(quote),
                "supplier_name": suppliers[quote.supplier_id].name
                if quote.supplier_id in suppliers
                else quote.supplier_name,
                "lines": line_results,
                "subtotal": str(subtotal),
                "total": str(total) if total is not None else None,
                "lead_time_days": max(leads) if leads else None,
                "delivery_date": str(latest) if latest else None,
                "alerts": alerts,
                "eligible": eligible,
                "reliability": str(reliability),
                "historical_orders": len(supplier_history),
            }
        )
    comparable = [
        r
        for r in results
        if r["currency"] == rfq.currency
        and r["total"] is not None
        and not any(
            a["code"] in ("INCOMPLETE_SCOPE", "QUANTITY_MISMATCH", "UOM_MISMATCH", "UNMATCHED_ITEM")
            for a in r["alerts"]
        )
    ]
    lowest = min((D(r["total"]) for r in comparable), default=D(0))
    fastest = min((r["lead_time_days"] for r in comparable if r["lead_time_days"] is not None), default=0)
    for row in results:
        factors = {
            "price": money((min(D(1), lowest / D(row["total"])) if D(row["total"]) > 0 else D(1)) * weights["price"])
            if row in comparable
            else D(0),
            "lead_time": money(min(D(1), D(fastest + 1) / D(row["lead_time_days"] + 1)) * weights["lead_time"])
            if row["lead_time_days"] is not None
            else D(0),
            "reliability": money(D(row["reliability"]) * weights["reliability"]),
            "fit": D(weights["fit"]) if row["eligible"] else D(0),
        }
        row["factors"] = {k: str(v) for k, v in factors.items()}
        row["score"] = str(money(sum(factors.values()))) if row["currency"] == rfq.currency else None
        row["lowest_cost"] = row in comparable and D(row["total"]) == lowest
        row["fastest"] = row["lead_time_days"] == fastest and row in comparable
    ranked = sorted(
        [r for r in results if r["eligible"]], key=lambda r: (-D(r["score"]), D(r["total"]), r["supplier_name"])
    )
    winner = ranked[0] if ranked else None
    savings = max((D(r["total"]) for r in comparable), default=D(0)) - D(winner["total"]) if winner else D(0)
    explanation = (
        f"{winner['supplier_name']} ranks first at {winner['score']}/100 with an evaluated total of {rfq.currency} {D(winner['total']):,.2f}. It covers all required items, meets the delivery target, and has no MOQ conflicts."
        if winner
        else "No supplier currently satisfies all requirements. Resolve blocking review findings before generating a recommendation."
    )
    return {
        "rfq": serialize(rfq),
        "requirements": [
            {
                **serialize(r),
                **{
                    "sku": items[r.item_id].sku,
                    "description": items[r.item_id].description,
                    "uom": items[r.item_id].uom,
                },
            }
            for r in requirements
        ],
        "quotes": results,
        "weights": weights,
        "recommended_quote_id": winner["id"] if winner else None,
        "explanation": explanation,
        "potential_savings": str(money(max(savings, D(0)))),
        "savings_basis": "Highest comparable complete quote minus recommended quote; excludes FX and incomplete scope.",
        "as_of": str(today),
    }


def refresh_alerts(db, org, rfq, actor=None):
    data = comparison(db, org, rfq)
    for q in data["quotes"]:
        old = {
            (a.code, a.message)
            for a in db.scalars(select(Alert).where(Alert.organization_id == org, Alert.quote_id == q["id"]))
        }
        db.execute(delete(Alert).where(Alert.organization_id == org, Alert.quote_id == q["id"]))
        for a in q["alerts"]:
            db.add(Alert(organization_id=org, quote_id=q["id"], **a))
            if (a["code"], a["message"]) not in old:
                audit(db, org, actor, "ALERT_CREATED", "quote", q["id"], new=a)
    return data
