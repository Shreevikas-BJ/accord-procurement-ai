import logging
import os
import time
import copy
from decimal import Decimal
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


def persist_extraction(db, document, extraction: QuoteExtraction, provider, diagnostics=None):
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
    diagnostics = dict(diagnostics or {})
    if provider == "local" and not supplier:
        diagnostics.setdefault("findings", []).append(
            {
                "code": "SUPPLIER_UNMATCHED",
                "field": "supplier_name",
                "message": "Supplier requires confirmation against this organization's catalog.",
            }
        )
        diagnostics.update(confidence_band="LOW", needs_review=True)
        extraction.confidence = min(extraction.confidence, Decimal("0.4"))
    extraction_record = DocumentExtraction(
        organization_id=org, document_id=document.id, provider=provider, payload=payload, diagnostics={}
    )
    db.add(extraction_record)
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
    line_ids = {}
    for index, line in enumerate(extraction.line_items):
        item, method, _ = match_item(
            db, org, quote.supplier_id, line.supplier_sku, line.manufacturer_part_number, line.description
        )
        fields = line.model_dump(exclude={"source_references", "price_tiers"})
        if provider == "local" and not item:
            diagnostics.setdefault("findings", []).append(
                {
                    "code": "SKU_UNMATCHED",
                    "field": "supplier_sku",
                    "message": "Catalog item requires buyer confirmation.",
                }
            )
            diagnostics.update(confidence_band="LOW", needs_review=True)
            quote.confidence = min(quote.confidence, Decimal("0.4"))
        refs = line.model_dump(mode="json")["source_references"]
        for ref in refs.values():
            ref["document_id"] = document.id
        record = QuoteItem(
            organization_id=org,
            quote_id=quote.id,
            item_id=item.id if item else None,
            match_method=method,
            source_references=refs,
            price_tiers=line.model_dump(mode="json")["price_tiers"],
            **fields,
        )
        db.add(record)
        db.flush()
        line_ids[record.id] = index
    document.rfq_id = quote.rfq_id
    document.classification = "Supplier Quotation"
    document.status = "Needs Review"
    document.stage = "Review Required" if not supplier or not rfq else "Complete"
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
        comparison = refresh_alerts(db, org, rfq, document.uploaded_by)
        if provider == "local":
            result = next(row for row in comparison["quotes"] if row["id"] == quote.id)
            diagnostics["procurement_findings"] = result["alerts"]
            if any(a["code"] == "PRICE_INCREASE" for a in result["alerts"]):
                diagnostics.update(confidence_band="LOW", needs_review=True)
                diagnostics.setdefault("findings", []).append(
                    {
                        "code": "HISTORICAL_PRICE_ANOMALY",
                        "field": "unit_price",
                        "message": "Extracted price exceeds the configured historical anomaly threshold.",
                    }
                )
                quote.confidence = min(quote.confidence, Decimal("0.4"))
    diagnostics["line_ids"] = line_ids
    extraction_record.diagnostics = copy.deepcopy(diagnostics)
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
            started = time.monotonic()
            diagnostics = {}
            stage("Reading Document")
            path = LocalStorageProvider().path(document.storage_key)
            stage("Extracting Text")
            document_input = None
            if os.getenv("AI_MODE", "demo") == "local":
                from .document_input import prepare_document

                document_input = prepare_document(path)
                text = document_input.text
            else:
                text = parser_for(document.filename).parse(path)
            document.raw_text = text[:200000]
            stage("Extracting Quote")
            extraction, provider = extract_quote(
                text, document.sha256, document_input, diagnostics, allow_fallback=False
            )
            diagnostics["total_seconds"] = round(time.monotonic() - started, 4)
            stage("Matching Supplier")
            stage("Matching Items")
            stage("Analyzing Pricing")
            # Reacquire the row after progress commits before persisting a result.
            db.refresh(document, with_for_update=True)
            if db.scalar(
                select(Quote).where(Quote.organization_id == organization_id, Quote.document_id == document_id)
            ):
                return
            persist_extraction(db, document, extraction, provider, diagnostics)
            db.commit()
        except Exception as error:
            db.rollback()
            document = db.get(Document, document_id)
            if os.getenv("AI_MODE", "demo") == "local":
                diagnostics.update(
                    success=False, error_type=type(error).__name__, total_seconds=round(time.monotonic() - started, 4)
                )
                db.add(
                    DocumentExtraction(
                        organization_id=organization_id,
                        document_id=document_id,
                        provider="local",
                        payload={},
                        diagnostics=diagnostics,
                    )
                )
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
