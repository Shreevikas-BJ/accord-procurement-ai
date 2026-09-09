import csv
import io
import os
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ValidationError
from .db import get_db
from .auth import current_user, admin, buyer
from .common import owned, serialize, audit
from .models import (
    Supplier,
    SupplierContact,
    Item,
    ItemAlias,
    RFQ,
    PurchaseHistory,
    AuditEvent,
    Document,
    Quote,
    Alert,
    ScoringSettings,
    Organization,
    User,
)
from .engine import comparison, money, average, refresh_alerts
from .schemas import SettingsInput, Money, Quantity, ItemInput
from .pipeline import invalidate

router = APIRouter()
CATALOG = {
    "rfqs": (RFQ, ["number", "title", "status"]),
    "suppliers": (Supplier, ["name", "category", "status"]),
    "items": (Item, ["sku", "description", "category"]),
    "purchase-history": (PurchaseHistory, ["po_number", "currency"]),
    "audit-events": (AuditEvent, ["action", "entity_type"]),
    "documents": (Document, ["filename", "status", "stage"]),
    "quotes": (Quote, ["supplier_name", "quote_number", "review_status"]),
    "alerts": (Alert, ["code", "message"]),
}


def list_records(kind, db, org, search="", status="", page=1, limit=25, sort="created_at", direction="desc"):
    model, fields = CATALOG[kind]
    stmt = select(model).where(model.organization_id == org)
    if search:
        conditions = [getattr(model, key).ilike("%" + search + "%") for key in fields]
        if kind == "purchase-history":
            conditions.extend(
                [
                    PurchaseHistory.supplier_id.in_(
                        select(Supplier.id).where(
                            Supplier.organization_id == org, Supplier.name.ilike("%" + search + "%")
                        )
                    ),
                    PurchaseHistory.item_id.in_(
                        select(Item.id).where(
                            Item.organization_id == org,
                            or_(Item.sku.ilike("%" + search + "%"), Item.description.ilike("%" + search + "%")),
                        )
                    ),
                ]
            )
        stmt = stmt.where(or_(*conditions))
    if status and hasattr(model, "status"):
        stmt = stmt.where(model.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = getattr(model, sort) if sort in fields + ["created_at"] else model.created_at
    if kind == "purchase-history" and sort == "created_at":
        order = PurchaseHistory.date
    rows = db.scalars(
        stmt.order_by(order.asc() if direction == "asc" else order.desc(), model.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    result = [serialize(r) for r in rows]
    if kind == "audit-events":
        names = {u.id: u.name for u in db.scalars(select(User).where(User.organization_id == org))}
        for row in result:
            row["actor_name"] = names.get(row["user_id"], "System")
    if kind in ("items", "suppliers", "purchase-history"):
        suppliers = {s.id: s.name for s in db.scalars(select(Supplier).where(Supplier.organization_id == org))}
        items = {i.id: i for i in db.scalars(select(Item).where(Item.organization_id == org))}
        for r in result:
            if "supplier_id" in r:
                r["supplier_name"] = suppliers.get(r["supplier_id"], "")
            if "item_id" in r:
                r["sku"] = items[r["item_id"]].sku
                r["description"] = items[r["item_id"]].description
            if kind == "purchase-history":
                r["total"] = str(money(Decimal(r["quantity"]) * Decimal(r["unit_price"])))
    if kind == "rfqs":
        counts = dict(
            db.execute(
                select(Quote.rfq_id, func.count()).where(Quote.organization_id == org).group_by(Quote.rfq_id)
            ).all()
        )
        for r in result:
            r["response_count"] = counts.get(r["id"], 0)
    if kind == "documents":
        quotes = {
            q.document_id: q
            for q in db.scalars(
                select(Quote).where(Quote.organization_id == org, Quote.document_id.in_([r["id"] for r in result]))
            )
        }
        rfqs = {r.id: r.number for r in db.scalars(select(RFQ).where(RFQ.organization_id == org))}
        for r in result:
            q = quotes.get(r["id"])
            r.pop("raw_text", None)
            r.pop("storage_key", None)
            r["quote_id"] = q.id if q else None
            r["supplier_name"] = q.supplier_name if q else "Awaiting extraction"
            r["rfq_number"] = rfqs.get(r["rfq_id"])
    return {"items": result, "total": total, "page": page, "limit": limit}


@router.get("/dashboard")
def dashboard(user=Depends(current_user), db: Session = Depends(get_db)):
    org = user.organization_id
    rfqs = db.scalars(select(RFQ).where(RFQ.organization_id == org)).all()
    comparisons = [comparison(db, org, r) for r in rfqs]
    quotes = [q for c in comparisons for q in c["quotes"]]
    alerts = [{**a, "supplier_name": q["supplier_name"], "quote_id": q["id"]} for q in quotes for a in q["alerts"]]
    docs = db.scalars(select(Document).where(Document.organization_id == org, Document.processed_at.is_not(None))).all()
    seconds = [(d.processed_at.replace(tzinfo=None) - d.created_at.replace(tzinfo=None)).total_seconds() for d in docs]
    primary_currency = db.get(Organization, org).currency
    return {
        "metrics": {
            "open_rfqs": sum(r.status not in ("Closed", "Awarded") for r in rfqs),
            "quotes_received": len(quotes),
            "needs_review": sum(q["review_status"] != "Reviewed" for q in quotes),
            "awaiting_response": sum(max(0, c["rfq"]["supplier_count"] - len(c["quotes"])) for c in comparisons),
            "potential_savings": str(
                sum(
                    (Decimal(c["potential_savings"]) for c in comparisons if c["rfq"]["currency"] == primary_currency),
                    Decimal(0),
                )
            ),
            "processing_seconds": round(sum(seconds) / len(seconds), 1) if seconds else None,
            "currency": primary_currency,
        },
        "rfqs": [
            {**c["rfq"], "response_count": len(c["quotes"]), "potential_savings": c["potential_savings"]}
            for c in comparisons
        ],
        "alerts": alerts[:12],
        "activity": list_records("audit-events", db, org, limit=8)["items"],
    }


@router.get("/settings/scoring")
def settings(user=Depends(current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id)
    row = db.scalar(select(ScoringSettings).where(ScoringSettings.organization_id == org.id))
    return {
        **serialize(row),
        "organization_name": org.name,
        "currency": org.currency,
        "ai_mode": os.getenv("AI_MODE", "demo"),
        "ai_model": os.getenv("AI_MODEL", ""),
        "ocr_provider": "Tesseract CPU",
        "storage_provider": "Local filesystem",
    }


@router.put("/settings/scoring")
def update_settings(payload: SettingsInput, user=Depends(admin), db: Session = Depends(get_db)):
    row = db.scalar(
        select(ScoringSettings).where(ScoringSettings.organization_id == user.organization_id).with_for_update()
    )
    old = serialize(row)
    for k, v in payload.model_dump(exclude={"organization_name", "currency"}).items():
        setattr(row, k, v)
    org = db.get(Organization, user.organization_id)
    org.name, org.currency = payload.organization_name, payload.currency
    db.flush()
    for rfq in db.scalars(select(RFQ).where(RFQ.organization_id == org.id).order_by(RFQ.id).with_for_update()):
        invalidate(db, rfq)
        refresh_alerts(db, org.id, rfq, user.id)
    audit(db, org.id, user.id, "SETTINGS_UPDATED", "settings", row.id, old, payload.model_dump(mode="json"))
    db.commit()
    return settings(user, db)


class HistoryImport(BaseModel):
    po_number: str = Field(min_length=1, max_length=100)
    date: date
    supplier: str
    sku: str
    quantity: Quantity
    unit_price: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    uom: str
    lead_time_days: int = Field(ge=0, le=3650)
    expected_delivery: date
    actual_delivery: date | None = None


@router.post("/purchase-history/import", status_code=201)
async def import_history(file: UploadFile, user=Depends(admin), db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Upload a CSV file using the sample import schema.")
    content = await file.read(5_000_001)
    if len(content) > 5_000_000:
        raise HTTPException(413, "Import is limited to 5 MB.")
    try:
        raw = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        if not raw or len(raw) > 10000:
            raise ValueError("Import must contain 1–10,000 rows.")
        rows = [
            HistoryImport.model_validate({k: (None if k == "actual_delivery" and not v else v) for k, v in r.items()})
            for r in raw
        ]
    except (ValueError, ValidationError) as error:
        raise HTTPException(422, f"Invalid CSV: {str(error)[:300]}") from error
    suppliers = {
        s.name: s.id for s in db.scalars(select(Supplier).where(Supplier.organization_id == user.organization_id))
    }
    items = {i.sku: i for i in db.scalars(select(Item).where(Item.organization_id == user.organization_id))}
    existing = set(
        db.execute(
            select(PurchaseHistory.po_number, PurchaseHistory.item_id).where(
                PurchaseHistory.organization_id == user.organization_id
            )
        ).all()
    )
    for index, row in enumerate(rows, 2):
        if row.supplier not in suppliers or row.sku not in items or row.uom != items[row.sku].uom:
            raise HTTPException(422, f"Row {index}: unknown supplier, SKU, or inconsistent UOM.")
        pair = (row.po_number, items[row.sku].id)
        if pair in existing:
            raise HTTPException(409, f"Row {index}: duplicate PO/item combination. No rows imported.")
        existing.add(pair)
        db.add(
            PurchaseHistory(
                organization_id=user.organization_id,
                supplier_id=suppliers[row.supplier],
                item_id=items[row.sku].id,
                **row.model_dump(exclude={"supplier", "sku"}),
            )
        )
    db.flush()
    for rfq in db.scalars(
        select(RFQ).where(RFQ.organization_id == user.organization_id).order_by(RFQ.id).with_for_update()
    ):
        invalidate(db, rfq)
        refresh_alerts(db, user.organization_id, rfq, user.id)
    audit(
        db,
        user.organization_id,
        user.id,
        "HISTORY_IMPORTED",
        "organization",
        user.organization_id,
        new={"rows": len(rows)},
    )
    db.commit()
    return {"imported": len(rows)}


@router.get("/suppliers/{id}")
def supplier_detail(id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    supplier = owned(db, Supplier, id, user.organization_id)
    history = db.scalars(
        select(PurchaseHistory).where(
            PurchaseHistory.organization_id == user.organization_id, PurchaseHistory.supplier_id == id
        )
    ).all()
    spend = {}
    for h in history:
        spend[h.currency] = str(Decimal(spend.get(h.currency, "0")) + money(h.quantity * h.unit_price))
    return {
        **serialize(supplier),
        "contacts": [
            serialize(c)
            for c in db.scalars(
                select(SupplierContact).where(
                    SupplierContact.organization_id == user.organization_id, SupplierContact.supplier_id == id
                )
            )
        ],
        "metrics": {
            "spend_by_currency": spend,
            "order_count": len(history),
            "average_lead_time": str(money(average([Decimal(h.lead_time_days) for h in history]))) if history else None,
            "on_time_orders": sum(
                h.actual_delivery is not None and h.actual_delivery <= h.expected_delivery for h in history
            ),
        },
        "quotes": [
            serialize(q)
            for q in db.scalars(
                select(Quote).where(Quote.organization_id == user.organization_id, Quote.supplier_id == id)
            )
        ],
        "history": [serialize(h) for h in sorted(history, key=lambda h: h.date, reverse=True)[:30]],
    }


@router.get("/items/{id}")
def item_detail(id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db, Item, id, user.organization_id)
    rows = db.scalars(
        select(PurchaseHistory)
        .where(PurchaseHistory.organization_id == user.organization_id, PurchaseHistory.item_id == id)
        .order_by(PurchaseHistory.date.desc())
        .limit(100)
    ).all()
    return {
        **serialize(item),
        "aliases": [
            a.alias
            for a in db.scalars(
                select(ItemAlias).where(ItemAlias.organization_id == user.organization_id, ItemAlias.item_id == id)
            )
        ],
        "history": [serialize(h) for h in rows],
    }


@router.post("/items", status_code=201)
def create_item(payload: ItemInput, user=Depends(buyer), db: Session = Depends(get_db)):
    item = Item(organization_id=user.organization_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, user.organization_id, user.id, "ITEM_CREATED", "item", item.id, new=serialize(item))
    db.commit()
    return serialize(item)


# Register explicit catalog routes last, so detail and import endpoints keep priority.
def make_list(kind):
    def endpoint(
        search: str = Query("", max_length=200),
        status: str = "",
        page: int = Query(1, ge=1),
        limit: int = Query(25, ge=1, le=250),
        sort: str = "created_at",
        direction: str = "desc",
        user=Depends(current_user),
        db: Session = Depends(get_db),
    ):
        return list_records(kind, db, user.organization_id, search, status, page, limit, sort, direction)

    return endpoint


for kind in CATALOG:
    router.add_api_route("/" + kind, make_list(kind), methods=["GET"], name="list_" + kind)
