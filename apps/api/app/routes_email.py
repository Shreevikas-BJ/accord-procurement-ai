import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from redis import Redis
from rq import Queue
from rq.job import Callback
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth import buyer, current_user
from .common import audit, owned, serialize
from .config import MAX_UPLOAD, REDIS_URL
from .db import get_db
from .email_intake import (
    DuplicateEmailError,
    email_detail,
    persist_email,
    process_email,
)
from .email_matching import normalized_email, normalized_supplier_name
from .email_parser import MAX_EMAIL_BYTES, ParsedAttachment, parse_eml, parse_pasted
from .models import (
    EmailAttachment,
    EmailEvidence,
    EmailFieldConflict,
    ProcurementEmail,
    Quote,
    QuoteItem,
    Supplier,
    SupplierContact,
)
from .providers import LocalStorageProvider
from .schemas import EmailFieldConfirmation, EmailPasteInput, SupplierResolution


router = APIRouter(prefix="/emails", tags=["email intake"])


def email_job_failed(job, connection, exc_type, exc_value, traceback):
    email_id, organization_id = job.args
    from .db import SessionLocal

    with SessionLocal() as db:
        email = db.scalar(
            select(ProcurementEmail).where(
                ProcurementEmail.id == email_id,
                ProcurementEmail.organization_id == organization_id,
            )
        )
        if email and email.status not in {"COMPLETE", "NEEDS_REVIEW"}:
            email.status = "FAILED"
            email.status_reason = "Email processing timed out or the worker failed. Retry from Procurement Inbox."
            audit(
                db,
                organization_id,
                email.ingested_by,
                "EMAIL_PROCESSING_FAILED",
                "procurement_email",
                email.id,
                details={"error_type": exc_type.__name__},
            )
            db.commit()


def enqueue_email(db, email: ProcurementEmail):
    try:
        Queue("documents", connection=Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)).enqueue(
            process_email,
            email.id,
            email.organization_id,
            job_timeout=900,
            result_ttl=3600,
            on_failure=Callback(email_job_failed),
        )
        email.status = "RECEIVED"
    except Exception:
        email.status = "FAILED"
        email.status_reason = "The processing queue is unavailable. Start Redis and the worker, then retry."
    db.commit()


def _accepted(email: ProcurementEmail) -> dict:
    return {"id": email.id, "status": email.status, "thread_id": email.thread_id, "duplicate": False}


@router.post("/upload", status_code=202)
async def upload_eml(file: UploadFile, user=Depends(buyer), db: Session = Depends(get_db)):
    if Path(file.filename or "").suffix.casefold() != ".eml":
        raise HTTPException(415, "Upload an RFC 5322 .eml file.")
    content = await file.read(MAX_EMAIL_BYTES + 1)
    try:
        parsed = parse_eml(content)
        email = persist_email(db, user, parsed, "EML")
    except DuplicateEmailError as error:
        return {"id": error.email_id, "status": "DUPLICATE", "duplicate": True}
    except ValueError as error:
        raise HTTPException(413 if len(content) > MAX_EMAIL_BYTES else 422, str(error)) from error
    enqueue_email(db, email)
    return _accepted(email)


@router.post("/paste", status_code=202)
def paste_email(payload: EmailPasteInput, user=Depends(buyer), db: Session = Depends(get_db)):
    parsed = parse_pasted(
        raw_email=payload.raw_email,
        sender=payload.sender,
        recipients=payload.to,
        cc=payload.cc,
        subject=payload.subject,
        sent_at=payload.sent_at,
        message_id=payload.message_id,
        in_reply_to=payload.in_reply_to,
        references=payload.references,
        body_text=payload.body_text,
        body_html=payload.body_html,
    )
    try:
        email = persist_email(db, user, parsed, "PASTED", payload.rfq_id)
    except DuplicateEmailError as error:
        return {"id": error.email_id, "status": "DUPLICATE", "duplicate": True}
    enqueue_email(db, email)
    return _accepted(email)


@router.post("/paste-with-attachments", status_code=202)
async def paste_with_attachments(
    sender: str = Form(""),
    subject: str = Form(""),
    body_text: str = Form(""),
    sent_at: str | None = Form(None),
    message_id: str | None = Form(None),
    in_reply_to: str | None = Form(None),
    references: str = Form("[]"),
    rfq_id: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    user=Depends(buyer),
    db: Session = Depends(get_db),
):
    if len(files) > 50:
        raise HTTPException(413, "An email may contain at most 50 attachments.")
    try:
        reference_values = json.loads(references)
        parsed_at = datetime.fromisoformat(sent_at.replace("Z", "+00:00")) if sent_at else None
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(422, "Invalid sent_at or references metadata.") from error
    attachments = []
    for file in files:
        content = await file.read(MAX_UPLOAD + 1)
        if not content or len(content) > MAX_UPLOAD:
            raise HTTPException(413, "Attachments must be nonempty and no larger than 15 MB each.")
        attachments.append(ParsedAttachment(file.filename or "attachment", file.content_type or "", content))
    parsed = parse_pasted(
        sender=sender,
        subject=subject,
        body_text=body_text,
        sent_at=parsed_at,
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=reference_values,
    )
    try:
        email = persist_email(db, user, parsed, "PASTED_WITH_ATTACHMENTS", rfq_id, attachments)
    except DuplicateEmailError as error:
        return {"id": error.email_id, "status": "DUPLICATE", "duplicate": True}
    enqueue_email(db, email)
    return _accepted(email)


@router.get("")
def list_emails(
    search: str = Query("", max_length=200),
    status: str = Query("", max_length=60),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    statement = select(ProcurementEmail).where(ProcurementEmail.organization_id == user.organization_id)
    if search:
        statement = statement.where(
            or_(
                ProcurementEmail.subject.ilike(f"%{search}%"),
                ProcurementEmail.sender_email.ilike(f"%{search}%"),
                ProcurementEmail.sender_name.ilike(f"%{search}%"),
            )
        )
    if status:
        statement = statement.where(ProcurementEmail.status == status)
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = db.scalars(
        statement.order_by(ProcurementEmail.sent_at.desc(), ProcurementEmail.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    suppliers = {
        row.id: row.name
        for row in db.scalars(select(Supplier).where(Supplier.organization_id == user.organization_id))
    }
    attachment_counts = dict(
        db.execute(
            select(EmailAttachment.email_id, func.count(EmailAttachment.id))
            .where(EmailAttachment.organization_id == user.organization_id)
            .group_by(EmailAttachment.email_id)
        ).all()
    )
    return {
        "items": [
            {
                **serialize(row),
                "supplier_name": suppliers.get(row.supplier_id, row.sender_name or row.sender_email or "Unmatched"),
                "attachment_count": attachment_counts.get(row.id, 0),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/{email_id}")
def get_email(email_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    email = owned(db, ProcurementEmail, email_id, user.organization_id)
    return email_detail(db, email)


@router.get("/{email_id}/attachments/{attachment_id}/file")
def attachment_file(
    email_id: str,
    attachment_id: str,
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    owned(db, ProcurementEmail, email_id, user.organization_id)
    attachment = db.scalar(
        select(EmailAttachment).where(
            EmailAttachment.id == attachment_id,
            EmailAttachment.email_id == email_id,
            EmailAttachment.organization_id == user.organization_id,
        )
    )
    if not attachment:
        raise HTTPException(404, "Attachment not found in your organization.")
    path = LocalStorageProvider().path(attachment.storage_path)
    if not path.exists():
        raise HTTPException(404, "Stored attachment is missing.")
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,
        content_disposition_type="inline" if Path(attachment.filename).suffix.casefold() == ".pdf" else "attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.post("/{email_id}/retry", status_code=202)
def retry(email_id: str, user=Depends(buyer), db: Session = Depends(get_db)):
    email = owned(db, ProcurementEmail, email_id, user.organization_id)
    if email.status not in {"FAILED", "NEEDS_REVIEW"} or email.quote_id:
        raise HTTPException(409, "Only unprocessed failed or review emails can be retried.")
    email.status = "RECEIVED"
    email.status_reason = None
    db.commit()
    enqueue_email(db, email)
    return _accepted(email)


@router.post("/{email_id}/fields/confirm")
def confirm_field(
    email_id: str,
    payload: EmailFieldConfirmation,
    user=Depends(buyer),
    db: Session = Depends(get_db),
):
    email = owned(db, ProcurementEmail, email_id, user.organization_id)
    if not email.quote_id:
        raise HTTPException(409, "This email does not have a structured quote.")
    evidence = db.scalar(
        select(EmailEvidence)
        .where(
            EmailEvidence.organization_id == user.organization_id,
            EmailEvidence.email_id == email.id,
            EmailEvidence.field == payload.field,
        )
        .order_by(EmailEvidence.created_at.desc())
    )
    if not evidence:
        raise HTTPException(422, "The field has no email or attachment evidence.")
    candidate = payload.value if payload.value is not None else evidence.value.get("value")
    quote = owned(db, Quote, email.quote_id, user.organization_id)
    if payload.field.startswith("line_items."):
        parts = payload.field.split(".")
        if len(parts) != 3 or not parts[1].isdigit():
            raise HTTPException(422, "Invalid line-item field path.")
        rows = db.scalars(
            select(QuoteItem)
            .where(QuoteItem.organization_id == user.organization_id, QuoteItem.quote_id == quote.id)
            .order_by(QuoteItem.created_at, QuoteItem.id)
        ).all()
        index, field = int(parts[1]), parts[2]
        if index >= len(rows) or field not in {"quantity", "unit_price", "moq", "lead_time_days", "supplier_sku", "uom"}:
            raise HTTPException(422, "Unsupported line-item confirmation field.")
        setattr(rows[index], field, candidate)
    elif payload.field in {"currency", "payment_terms", "shipping_terms", "shipping_cost", "tax", "quote_number"}:
        setattr(quote, payload.field, candidate)
    else:
        raise HTTPException(422, "Unsupported confirmation field.")
    evidence.decision_status = "ACCEPTED"
    evidence.reason = f"Confirmed by {user.id}"
    for conflict in db.scalars(
        select(EmailFieldConflict).where(
            EmailFieldConflict.organization_id == user.organization_id,
            EmailFieldConflict.email_id == email.id,
            EmailFieldConflict.field == payload.field,
        )
    ):
        conflict.resolution = "BUYER_CONFIRMED"
    quote.version += 1
    audit(
        db,
        user.organization_id,
        user.id,
        "EMAIL_FIELD_CONFIRMED",
        "procurement_email",
        email.id,
        new={"field": payload.field, "value": candidate},
    )
    db.commit()
    return {"email_id": email.id, "quote_id": quote.id, "field": payload.field, "value": candidate}


@router.post("/{email_id}/supplier")
def resolve_supplier(
    email_id: str,
    payload: SupplierResolution,
    user=Depends(buyer),
    db: Session = Depends(get_db),
):
    email = owned(db, ProcurementEmail, email_id, user.organization_id)
    if payload.action == "REVIEW_LATER":
        email.status = "NEEDS_REVIEW"
        db.commit()
        return {"email_id": email.id, "supplier_id": email.supplier_id, "status": email.status}
    if payload.action == "VERIFY":
        if not email.supplier_id:
            raise HTTPException(409, "No supplier is associated with this email.")
        supplier = owned(db, Supplier, email.supplier_id, user.organization_id)
        supplier.status = "VERIFIED"
    elif payload.action == "USE_EXISTING":
        if not payload.supplier_id:
            raise HTTPException(422, "supplier_id is required.")
        supplier = owned(db, Supplier, payload.supplier_id, user.organization_id)
        email.supplier_id = supplier.id
        if email.quote_id:
            owned(db, Quote, email.quote_id, user.organization_id).supplier_id = supplier.id
    else:
        if email.supplier_id:
            raise HTTPException(409, "This email already has a supplier. Edit or verify that record.")
        name = email.sender_name or (email.sender_domain.split(".")[0].title() if email.sender_domain else "New Supplier")
        supplier = Supplier(
            organization_id=user.organization_id,
            name=name,
            normalized_name=normalized_supplier_name(name),
            aliases=[],
            category="Uncategorized",
            status="NEW_UNVERIFIED",
            email_domain=email.sender_domain,
            website="",
            currency="USD",
            payment_terms="Net 30",
            primary_email=email.sender_email or None,
            created_source="EMAIL_INTAKE_CONFIRMED",
            created_from_email_id=email.id,
            auto_created=False,
        )
        db.add(supplier)
        db.flush()
        email.supplier_id = supplier.id
        if email.sender_email:
            db.add(
                SupplierContact(
                    organization_id=user.organization_id,
                    supplier_id=supplier.id,
                    name=email.sender_name or "Email contact",
                    email=email.sender_email,
                    normalized_email=normalized_email(email.sender_email),
                    created_from_email_id=email.id,
                    auto_created=False,
                )
            )
    audit(
        db,
        user.organization_id,
        user.id,
        "SUPPLIER_MATCHED" if payload.action == "USE_EXISTING" else "SUPPLIER_VERIFIED",
        "procurement_email",
        email.id,
        new={"supplier_id": supplier.id, "action": payload.action},
    )
    db.commit()
    return {"email_id": email.id, "supplier_id": supplier.id, "supplier_status": supplier.status}
