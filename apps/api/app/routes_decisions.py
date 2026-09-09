from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .auth import current_user, buyer
from .models import RFQ, Recommendation, Quote, Approval, EmailDraft, Supplier
from .common import owned, serialize, audit
from .engine import comparison
from .schemas import ApprovalInput, DraftInput, DraftEdit
from .providers import DraftOnlyEmailProvider

router = APIRouter()


@router.post("/rfqs/{id}/recommendation", status_code=201)
def generate_recommendation(id: str, user=Depends(buyer), db: Session = Depends(get_db)):
    rfq = db.scalar(select(RFQ).where(RFQ.id == id, RFQ.organization_id == user.organization_id).with_for_update())
    if not rfq:
        raise HTTPException(404, "RFQ not found.")
    data = comparison(db, user.organization_id, rfq)
    if not data["recommended_quote_id"]:
        raise HTTPException(409, data["explanation"])
    rec = Recommendation(
        organization_id=user.organization_id,
        rfq_id=id,
        quote_id=data["recommended_quote_id"],
        revision=rfq.revision,
        explanation=data["explanation"],
        snapshot=data,
    )
    db.add(rec)
    db.flush()
    audit(
        db,
        user.organization_id,
        user.id,
        "RECOMMENDATION_GENERATED",
        "recommendation",
        rec.id,
        new={"quote_id": rec.quote_id, "revision": rec.revision},
    )
    db.commit()
    return serialize(rec)


@router.get("/rfqs/{id}/recommendation")
def get_recommendation(id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    owned(db, RFQ, id, user.organization_id)
    rec = db.scalar(
        select(Recommendation)
        .where(Recommendation.organization_id == user.organization_id, Recommendation.rfq_id == id)
        .order_by(Recommendation.created_at.desc())
    )
    return serialize(rec) if rec else None


@router.post("/approvals", status_code=201)
def approve(payload: ApprovalInput, user=Depends(buyer), db: Session = Depends(get_db)):
    rec = owned(db, Recommendation, payload.recommendation_id, user.organization_id)
    rfq = db.scalar(
        select(RFQ).where(RFQ.id == rec.rfq_id, RFQ.organization_id == user.organization_id).with_for_update()
    )
    db.refresh(rec)
    if rec.status == "Approved":
        raise HTTPException(409, "Recommendation is already approved.")
    data = comparison(db, user.organization_id, rfq)
    if rec.revision != rfq.revision or rec.status == "Stale" or data["recommended_quote_id"] != rec.quote_id:
        raise HTTPException(409, "Recommendation is stale. Generate a fresh recommendation before approving.")
    q = owned(db, Quote, rec.quote_id, user.organization_id)
    if q.review_status != "Reviewed":
        raise HTTPException(409, "Review and confirm the recommended supplier quote before approving.")
    approval = Approval(
        organization_id=user.organization_id, recommendation_id=rec.id, approved_by=user.id, note=payload.note
    )
    db.add(approval)
    rec.status = "Approved"
    rfq.status = "Under Review"
    audit(
        db,
        user.organization_id,
        user.id,
        "RECOMMENDATION_APPROVED",
        "recommendation",
        rec.id,
        new={
            "quote_id": rec.quote_id,
            "note": payload.note,
            "effect": "Internal decision recorded. No order or supplier commitment created.",
        },
    )
    db.commit()
    return serialize(approval)


@router.get("/approvals")
def approvals(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        serialize(a)
        for a in db.scalars(
            select(Approval)
            .where(Approval.organization_id == user.organization_id)
            .order_by(Approval.created_at.desc())
            .limit(100)
        )
    ]


@router.post("/quotes/{id}/preferred")
def preferred(id: str, user=Depends(buyer), db: Session = Depends(get_db)):
    quote = owned(db, Quote, id, user.organization_id)
    if not quote.supplier_id:
        raise HTTPException(409, "Confirm the supplier first.")
    supplier = owned(db, Supplier, quote.supplier_id, user.organization_id)
    supplier.preferred_supplier = True
    audit(db, user.organization_id, user.id, "SUPPLIER_MARKED_PREFERRED", "supplier", supplier.id)
    db.commit()
    return {"message": "Supplier marked preferred"}


@router.post("/email-drafts", status_code=201)
def draft(payload: DraftInput, user=Depends(buyer), db: Session = Depends(get_db)):
    quote = owned(db, Quote, payload.quote_id, user.organization_id)
    rfq = owned(db, RFQ, quote.rfq_id, user.organization_id)
    data = comparison(db, user.organization_id, rfq)
    evaluated = next(q for q in data["quotes"] if q["id"] == quote.id)
    body = DraftOnlyEmailProvider().draft(
        evaluated["supplier_name"],
        rfq.number,
        str(rfq.required_delivery),
        payload.kind,
        [a["message"] for a in evaluated["alerts"]],
    )
    row = EmailDraft(
        organization_id=user.organization_id,
        quote_id=quote.id,
        kind=payload.kind,
        subject=f"{rfq.number} — {payload.kind}",
        body=body,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        user.organization_id,
        user.id,
        "EMAIL_DRAFT_GENERATED",
        "email_draft",
        row.id,
        new={"quote_id": quote.id, "kind": payload.kind},
    )
    db.commit()
    return serialize(row)


@router.get("/email-drafts")
def drafts(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        serialize(a)
        for a in db.scalars(
            select(EmailDraft)
            .where(EmailDraft.organization_id == user.organization_id)
            .order_by(EmailDraft.created_at.desc())
            .limit(100)
        )
    ]


@router.put("/email-drafts/{id}")
def update_draft(id: str, payload: DraftEdit, user=Depends(buyer), db: Session = Depends(get_db)):
    row = owned(db, EmailDraft, id, user.organization_id)
    old = serialize(row)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    audit(
        db,
        user.organization_id,
        user.id,
        "EMAIL_DRAFT_APPROVED" if row.status == "Approved" else "EMAIL_DRAFT_EDITED",
        "email_draft",
        id,
        old,
        serialize(row),
    )
    db.commit()
    return serialize(row)
