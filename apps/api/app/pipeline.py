import logging
from datetime import datetime, timezone
from sqlalchemy import select
from .db import SessionLocal
from .models import Document, Quote, QuoteItem, DocumentExtraction, RFQ, Recommendation
from .schemas import QuoteExtraction
from .providers import LocalStorageProvider, parser_for, extract_quote
from .matching import match_supplier, match_item
from .common import audit
from .engine import refresh_alerts

log = logging.getLogger(__name__)


def invalidate(db, rfq):
    rfq.revision += 1
    for rec in db.scalars(
        select(Recommendation).where(
            Recommendation.organization_id == rfq.organization_id,
            Recommendation.rfq_id == rfq.id,
            Recommendation.status != "Stale",
        )
    ):
        rec.status = "Stale"
    if rfq.status == "Under Review":
        rfq.status = "Quotes Received"


def persist_extraction(db, document, extraction: QuoteExtraction, provider):
    org = document.organization_id
    supplier = match_supplier(db, org, extraction.supplier_name, extraction.supplier_email)
    rfq = (
        db.scalar(select(RFQ).where(RFQ.organization_id == org, RFQ.id == document.rfq_id).with_for_update())
        if document.rfq_id
        else db.scalar(
            select(RFQ).where(RFQ.organization_id == org, RFQ.number == extraction.rfq_number).with_for_update()
        )
    )
    payload = extraction.model_dump(mode="json")
    db.add(DocumentExtraction(organization_id=org, document_id=document.id, provider=provider, payload=payload))
    values = extraction.model_dump(exclude={"line_items", "source_references"})
    for ref in payload["source_references"].values():
        ref["document_id"] = document.id
    quote = Quote(
        organization_id=org,
        document_id=document.id,
        rfq_id=rfq.id if rfq else None,
        supplier_id=supplier.id if supplier else None,
        source_references=payload["source_references"],
        **values,
    )
    db.add(quote)
    db.flush()
    for line in extraction.line_items:
        item, method, _ = match_item(
            db, org, quote.supplier_id, line.supplier_sku, line.manufacturer_part_number, line.description
        )
        fields = line.model_dump(exclude={"source_references", "price_tiers"})
        refs = line.model_dump(mode="json")["source_references"]
        for ref in refs.values():
            ref["document_id"] = document.id
        db.add(
            QuoteItem(
                organization_id=org,
                quote_id=quote.id,
                item_id=item.id if item else None,
                match_method=method,
                source_references=refs,
                price_tiers=line.model_dump(mode="json")["price_tiers"],
                **fields,
            )
        )
    document.rfq_id = quote.rfq_id
    document.classification = "Supplier Quotation"
    document.status = "Needs Review"
    document.stage = "Complete"
    document.error = None if rfq else "RFQ not identified. Select the RFQ during review."
    document.processed_at = datetime.now(timezone.utc)
    audit(
        db,
        org,
        document.uploaded_by,
        "QUOTE_EXTRACTED",
        "quote",
        quote.id,
        details={"provider": provider, "document_id": document.id},
    )
    if supplier:
        audit(db, org, document.uploaded_by, "SUPPLIER_MATCHED", "quote", quote.id, new={"supplier_id": supplier.id})
    db.flush()
    if rfq:
        invalidate(db, rfq)
        refresh_alerts(db, org, rfq, document.uploaded_by)
    return quote


def process_document(document_id, organization_id):
    with SessionLocal() as db:
        document = db.scalar(
            select(Document)
            .where(Document.id == document_id, Document.organization_id == organization_id)
            .with_for_update()
        )
        if not document or db.scalar(
            select(Quote).where(Quote.document_id == document_id, Quote.organization_id == organization_id)
        ):
            return

        def stage(name):
            document.stage = name
            document.status = "Processing"
            db.commit()
            log.info("document_processing", extra={"document_id": document_id, "stage": name})

        try:
            stage("Reading Document")
            path = LocalStorageProvider().path(document.storage_key)
            stage("Extracting Text")
            text = parser_for(document.filename).parse(path)
            document.raw_text = text[:200000]
            stage("Extracting Quote")
            extraction, provider = extract_quote(text, document.sha256)
            stage("Matching Supplier")
            stage("Matching Items")
            stage("Analyzing Pricing")
            # Reacquire the row after progress commits before persisting a result.
            db.refresh(document, with_for_update=True)
            if db.scalar(
                select(Quote).where(Quote.organization_id == organization_id, Quote.document_id == document_id)
            ):
                return
            persist_extraction(db, document, extraction, provider)
            db.commit()
        except Exception as error:
            db.rollback()
            document = db.get(Document, document_id)
            document.status = "Needs Review"
            document.stage = "Review Required"
            document.error = (
                str(error)[:1000]
                if isinstance(error, ValueError)
                else "Document processing failed. Retry, upload a clearer file, or enter the quote manually."
            )
            audit(
                db,
                organization_id,
                document.uploaded_by,
                "PROCESSING_FAILED",
                "document",
                document_id,
                details={"error_type": type(error).__name__},
            )
            db.commit()
            log.error("processing_failed", extra={"document_id": document_id, "error_type": type(error).__name__})


def job_failed(job, connection, exc_type, exc_value, traceback):
    """RQ invokes this for timeouts and unhandled worker errors."""
    document_id, org = job.args
    with SessionLocal() as db:
        doc = db.scalar(select(Document).where(Document.id == document_id, Document.organization_id == org))
        if doc and doc.status in ("New", "Processing"):
            doc.status = "Error"
            doc.stage = "Worker failed"
            doc.error = "Processing timed out or the worker failed. Retry the document from the inbox."
            audit(
                db,
                org,
                doc.uploaded_by,
                "PROCESSING_FAILED",
                "document",
                doc.id,
                details={"error_type": exc_type.__name__},
            )
            db.commit()
