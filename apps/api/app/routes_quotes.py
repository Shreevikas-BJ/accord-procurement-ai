import hashlib
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
from rq.job import Callback
from .db import get_db
from .config import MAX_UPLOAD, REDIS_URL
from .auth import current_user, buyer
from .common import owned, serialize, audit
from .models import (
    Document,
    Quote,
    QuoteItem,
    RFQ,
    Supplier,
    Item,
    SupplierItemMapping,
    FieldCorrection,
    DocumentExtraction,
    uid,
)
from .providers import LocalStorageProvider
from .pipeline import process_document, persist_extraction, invalidate, job_failed
from .schemas import Review, PasteInput, QuoteExtraction
from .matching import match_item
from .engine import comparison, refresh_alerts, financials

router = APIRouter()
MIME = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".csv": {"text/csv", "application/vnd.ms-excel", "text/plain"},
    ".txt": {"text/plain"},
}


def enqueue(db, doc):
    try:
        Queue("documents", connection=Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)).enqueue(
            process_document,
            doc.id,
            doc.organization_id,
            job_timeout=600,
            result_ttl=3600,
            on_failure=Callback(job_failed),
        )
    except Exception:
        doc.status = "Error"
        doc.stage = "Queue unavailable"
        doc.error = "The processing queue is unavailable. Start Redis and the worker, then retry."
        db.commit()


def store_document(db, user, filename, mime, content, rfq_id):
    suffix = Path(filename).suffix.lower()
    if suffix not in MIME or mime not in MIME[suffix] | {"application/octet-stream"}:
        raise HTTPException(415, "Supported files: PDF, PNG, JPG, XLSX, CSV, and TXT. File type must match.")
    if not content or len(content) > MAX_UPLOAD:
        raise HTTPException(413, "Files must be nonempty and no larger than 15 MB.")
    signatures = {
        ".pdf": b"%PDF",
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8",
        ".jpeg": b"\xff\xd8",
        ".xlsx": b"PK",
    }
    if suffix in signatures and not content.startswith(signatures[suffix]):
        raise HTTPException(415, "File contents do not match the file extension.")
    if suffix in (".csv", ".txt"):
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise HTTPException(415, "Text and CSV files must use UTF-8 encoding.") from error
    if rfq_id:
        owned(db, RFQ, rfq_id, user.organization_id)
    digest = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(
        select(Document).where(Document.organization_id == user.organization_id, Document.sha256 == digest)
    )
    if duplicate:
        audit(db, user.organization_id, user.id, "DUPLICATE_DOCUMENT", "document", duplicate.id)
        db.commit()
        raise HTTPException(409, {"message": "This document was already uploaded.", "document_id": duplicate.id})
    id = uid()
    key = LocalStorageProvider().save(user.organization_id, id + suffix, content)
    safe_name = Path(filename.replace("\\", "/")).name[:200]
    doc = Document(
        id=id,
        organization_id=user.organization_id,
        filename=safe_name,
        mime_type=next(iter(MIME[suffix])),
        storage_key=key,
        sha256=digest,
        size=len(content),
        uploaded_by=user.id,
        rfq_id=rfq_id,
    )
    db.add(doc)
    audit(
        db,
        user.organization_id,
        user.id,
        "QUOTE_UPLOADED",
        "document",
        doc.id,
        new={"filename": safe_name, "size": len(content)},
    )
    db.commit()
    enqueue(db, doc)
    return {"id": doc.id, "status": doc.status, "stage": doc.stage}


@router.post("/quotes/upload", status_code=202)
async def upload(file: UploadFile, rfq_id: str | None = Form(None), user=Depends(buyer), db: Session = Depends(get_db)):
    content = await file.read(MAX_UPLOAD + 1)
    return store_document(db, user, file.filename or "", file.content_type or "", content, rfq_id)


@router.post("/quotes/paste", status_code=202)
def paste(payload: PasteInput, user=Depends(buyer), db: Session = Depends(get_db)):
    return store_document(db, user, payload.subject + ".txt", "text/plain", payload.text.encode(), payload.rfq_id)


@router.get("/documents/{id}")
def document(id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    doc = owned(db, Document, id, user.organization_id)
    quote = db.scalar(select(Quote).where(Quote.organization_id == user.organization_id, Quote.document_id == id))
    result = serialize(doc)
    result.pop("storage_key")
    return {**result, "quote_id": quote.id if quote else None}


@router.get("/documents/{id}/file")
def document_file(id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    doc = owned(db, Document, id, user.organization_id)
    path = LocalStorageProvider().path(doc.storage_key)
    if not path.exists():
        raise HTTPException(404, "Source file is missing. Re-upload the document.")
    return FileResponse(
        path,
        media_type=doc.mime_type,
        filename=doc.filename,
        content_disposition_type="inline"
        if Path(doc.filename).suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg")
        else "attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.post("/documents/{id}/retry", status_code=202)
def retry(id: str, user=Depends(buyer), db: Session = Depends(get_db)):
    doc = owned(db, Document, id, user.organization_id)
    if doc.status == "Processing" or db.scalar(
        select(Quote).where(Quote.organization_id == user.organization_id, Quote.document_id == id)
    ):
        raise HTTPException(409, "Document already processed or currently processing. Review the existing quote.")
    doc.status, doc.stage, doc.error = "New", "Queued", None
    audit(db, user.organization_id, user.id, "PROCESSING_RETRIED", "document", doc.id)
    db.commit()
    enqueue(db, doc)
    return {"id": id, "status": doc.status}


@router.post("/documents/{id}/manual", status_code=201)
def manual(id: str, payload: QuoteExtraction, user=Depends(buyer), db: Session = Depends(get_db)):
    doc = owned(db, Document, id, user.organization_id)
    if doc.status == "Processing" or db.scalar(
        select(Quote).where(Quote.organization_id == user.organization_id, Quote.document_id == id)
    ):
        raise HTTPException(409, "Document already has a quote or is processing.")
    quote = persist_extraction(db, doc, payload, "human manual entry")
    audit(db, user.organization_id, user.id, "MANUAL_QUOTE_ENTERED", "quote", quote.id)
    db.commit()
    return {"quote_id": quote.id}


@router.get("/quotes/{id}")
def quote_detail(id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    q = owned(db, Quote, id, user.organization_id)
    lines = db.scalars(
        select(QuoteItem)
        .where(QuoteItem.organization_id == user.organization_id, QuoteItem.quote_id == id)
        .order_by(QuoteItem.created_at, QuoteItem.id)
    ).all()
    totals, subtotal, total = financials(lines, q.shipping_cost, q.tax)
    items = []
    for line, line_total in zip(lines, totals):
        _, _, candidates = match_item(
            db, user.organization_id, q.supplier_id, line.supplier_sku, line.manufacturer_part_number, line.description
        )
        items.append(
            {
                **serialize(line),
                "line_total": str(line_total) if line_total is not None else None,
                "candidates": candidates,
            }
        )
    extraction = db.scalar(
        select(DocumentExtraction)
        .where(
            DocumentExtraction.organization_id == user.organization_id, DocumentExtraction.document_id == q.document_id
        )
        .order_by(DocumentExtraction.created_at.desc())
    )
    return {
        **serialize(q),
        "line_items": items,
        "subtotal": str(subtotal) if subtotal is not None else None,
        "total": str(total) if total is not None else None,
        "document": document(q.document_id, user, db),
        "extraction_provider": extraction.provider if extraction else "unknown",
        "extraction_diagnostics": extraction.diagnostics if extraction else {},
    }


@router.put("/quotes/{id}/review")
def review(id: str, payload: Review, user=Depends(buyer), db: Session = Depends(get_db)):
    q = owned(db, Quote, id, user.organization_id)
    affected = sorted({r for r in [q.rfq_id, payload.rfq_id] if r})
    rfqs = [
        db.scalar(select(RFQ).where(RFQ.organization_id == user.organization_id, RFQ.id == r).with_for_update())
        for r in affected
    ]
    if any(r is None for r in rfqs):
        raise HTTPException(404, "RFQ not found.")
    db.refresh(q)
    if q.version != payload.version:
        raise HTTPException(409, "This quote changed since you opened it. Reload before saving.")
    if payload.supplier_id:
        supplier = owned(db, Supplier, payload.supplier_id, user.organization_id)
        if payload.supplier_name and payload.supplier_name != supplier.name:
            supplier.aliases = list(set([*supplier.aliases, payload.supplier_name]))
    old = serialize(q)
    extraction = db.scalar(
        select(DocumentExtraction)
        .where(
            DocumentExtraction.organization_id == user.organization_id, DocumentExtraction.document_id == q.document_id
        )
        .order_by(DocumentExtraction.created_at.desc())
    )
    provenance = {
        "document_id": q.document_id,
        "extraction_id": extraction.id if extraction else None,
        **{
            k: (extraction.diagnostics or {}).get(k) if extraction else None
            for k in ("model", "prompt_version", "pipeline_version")
        },
    }
    fields = payload.model_dump(exclude={"line_items", "version", "confirm_review", "source_references"})
    for k, v in fields.items():
        setattr(q, k, v)
    # Source references stay immutable even when a human corrects the extracted value.
    if q.supplier_id != old["supplier_id"]:
        audit(
            db,
            user.organization_id,
            user.id,
            "SUPPLIER_MATCHED",
            "quote",
            id,
            old={"supplier_id": old["supplier_id"]},
            new={"supplier_id": q.supplier_id},
        )
    stored_lines = {
        x.id: x
        for x in db.scalars(
            select(QuoteItem).where(QuoteItem.organization_id == user.organization_id, QuoteItem.quote_id == id)
        )
    }
    if set(stored_lines) != {x.id for x in payload.line_items} or len(payload.line_items) != len(stored_lines):
        raise HTTPException(422, "Review must contain each existing quote line exactly once.")
    for line in payload.line_items:
        record = stored_lines[line.id]
        before = serialize(record)
        if line.item_id:
            owned(db, Item, line.item_id, user.organization_id)
        for k, v in line.model_dump(exclude={"id", "source_references", "price_tiers"}).items():
            setattr(record, k, v)
        record.price_tiers = line.model_dump(mode="json")["price_tiers"]
        if line.item_id and q.supplier_id:
            mapping = db.scalar(
                select(SupplierItemMapping).where(
                    SupplierItemMapping.organization_id == user.organization_id,
                    SupplierItemMapping.supplier_id == q.supplier_id,
                    SupplierItemMapping.supplier_sku == line.supplier_sku,
                )
            )
            if mapping:
                mapping.item_id = line.item_id
                mapping.confirmed_by = user.id
            else:
                db.add(
                    SupplierItemMapping(
                        organization_id=user.organization_id,
                        supplier_id=q.supplier_id,
                        supplier_sku=line.supplier_sku,
                        item_id=line.item_id,
                        confirmed_by=user.id,
                    )
                )
            record.match_method = "Confirmed mapping"
            if before["item_id"] != line.item_id or payload.confirm_review:
                audit(
                    db,
                    user.organization_id,
                    user.id,
                    "ITEM_MATCH_CONFIRMED",
                    "quote_item",
                    record.id,
                    new={"item_id": line.item_id, "supplier_sku": line.supplier_sku},
                )
        after = serialize(record)
        for key in before:
            if before[key] != after[key]:
                db.add(
                    FieldCorrection(
                        organization_id=user.organization_id,
                        quote_id=id,
                        field=f"line.{line.id}.{key}",
                        original_value={"value": before[key]},
                        corrected_value={"value": after[key]},
                        corrected_by=user.id,
                        provenance={
                            **provenance,
                            "original_ai_value": (
                                extraction.diagnostics.get("original_ai_payload") or extraction.payload
                            )
                            .get("line_items", [])[extraction.diagnostics["line_ids"][line.id]]
                            .get(key)
                            if extraction and line.id in (extraction.diagnostics or {}).get("line_ids", {})
                            else None,
                        },
                    )
                )
                audit(
                    db,
                    user.organization_id,
                    user.id,
                    "FIELD_CORRECTED",
                    "quote_item",
                    record.id,
                    old={key: before[key]},
                    new={key: after[key]},
                )
    q.version += 1
    q.review_status = "Reviewed" if payload.confirm_review else "Needs Review"
    doc = owned(db, Document, q.document_id, user.organization_id)
    doc.rfq_id = q.rfq_id
    doc.status = "Matched" if payload.confirm_review else "Needs Review"
    doc.error = None
    for key, value in old.items():
        current = serialize(q)[key]
        if value != current and key not in ("version", "review_status"):
            db.add(
                FieldCorrection(
                    organization_id=user.organization_id,
                    quote_id=id,
                    field=key,
                    original_value={"value": value},
                    corrected_value={"value": current},
                    corrected_by=user.id,
                    provenance={
                        **provenance,
                        "original_ai_value": (
                            extraction.diagnostics.get("original_ai_payload") or extraction.payload
                        ).get(key)
                        if extraction
                        else None,
                    },
                )
            )
    audit(
        db,
        user.organization_id,
        user.id,
        "QUOTE_REVIEWED" if payload.confirm_review else "FIELD_CORRECTED",
        "quote",
        id,
        old,
        serialize(q),
    )
    db.flush()
    for rfq in rfqs:
        invalidate(db, rfq)
        refresh_alerts(db, user.organization_id, rfq, user.id)
    db.commit()
    return quote_detail(id, user, db)


@router.get("/rfqs/{id}")
@router.get("/rfqs/{id}/comparison")
def rfq_comparison(id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    rfq = owned(db, RFQ, id, user.organization_id)
    return comparison(db, user.organization_id, rfq)
