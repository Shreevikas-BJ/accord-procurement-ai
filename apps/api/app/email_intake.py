"""Tenant-scoped orchestration for local procurement email intake."""

from __future__ import annotations

import copy
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import func, select

from .common import audit, serialize
from .db import SessionLocal
from .document_input import DocumentInput, prepare_document
from .email_extraction import SourceContext, candidate_has_quote, extract_candidate
from .email_matching import (
    GENERIC_DOMAINS,
    match_rfq,
    match_supplier_email,
    normalized_email,
    normalized_supplier_name,
    supplier_name_from_identity,
)
from .email_parser import ParsedAttachment, ParsedEmail, classify_email, html_content
from .email_reconciliation import reconcile_candidates
from .engine import refresh_alerts
from .matching import match_item
from .models import (
    Document,
    EmailAttachment,
    EmailEvidence,
    EmailFieldConflict,
    EmailThread,
    ProcurementEmail,
    Quote,
    QuoteItem,
    QuoteRevision,
    RFQ,
    Supplier,
    SupplierContact,
    SupplierMatchCandidate,
    User,
)
from .pipeline import invalidate, persist_extraction
from .providers import LocalStorageProvider, extract_quote


log = logging.getLogger(__name__)
PIPELINE_VERSION = "local-email-2.8.0"
PROMPT_VERSION = "email-intake-2.8.0"
SUPPORTED_ATTACHMENTS = {".pdf", ".xlsx", ".csv", ".txt"}
DEFERRED_ATTACHMENTS = {".png", ".jpg", ".jpeg"}


class DuplicateEmailError(ValueError):
    def __init__(self, email_id: str):
        super().__init__("This email was already ingested.")
        self.email_id = email_id


def _safe_filename(value: str) -> str:
    return Path((value or "attachment").replace("\\", "/")).name[:200] or "attachment"


def persist_email(
    db,
    user,
    parsed: ParsedEmail,
    source_type: str,
    explicit_rfq_id: str | None = None,
    extra_attachments: list[ParsedAttachment] | None = None,
) -> ProcurementEmail:
    duplicate = None
    if parsed.message_id:
        duplicate = db.scalar(
            select(ProcurementEmail).where(
                ProcurementEmail.organization_id == user.organization_id,
                ProcurementEmail.message_id == parsed.message_id,
            )
        )
    elif parsed.sender_email and parsed.sent_at:
        duplicate = db.scalar(
            select(ProcurementEmail).where(
                ProcurementEmail.organization_id == user.organization_id,
                ProcurementEmail.content_hash == parsed.content_hash,
                ProcurementEmail.sender_email == parsed.sender_email,
                ProcurementEmail.sent_at == parsed.sent_at,
            )
        )
    if duplicate:
        audit(db, user.organization_id, user.id, "DUPLICATE_EMAIL", "procurement_email", duplicate.id)
        db.commit()
        raise DuplicateEmailError(duplicate.id)
    email = ProcurementEmail(
        organization_id=user.organization_id,
        message_id=parsed.message_id,
        content_hash=parsed.content_hash,
        in_reply_to=parsed.in_reply_to,
        references=parsed.references,
        sender_name=parsed.sender_name,
        sender_email=parsed.sender_email,
        sender_domain=parsed.sender_domain,
        recipient_emails=parsed.recipients,
        cc_emails=parsed.cc,
        subject=parsed.subject or "(no subject)",
        normalized_subject=parsed.normalized_subject or "(no subject)",
        sent_at=parsed.sent_at,
        body_text=parsed.body_text,
        body_html=parsed.body_html,
        normalized_body=parsed.normalized_body,
        quoted_history=parsed.quoted_history,
        signature=parsed.signature,
        source_type=source_type,
        ingested_by=user.id,
        rfq_id=explicit_rfq_id,
        status="RECEIVED",
        status_reason="Missing From header; supplier identification requires review." if not parsed.sender_email else None,
    )
    db.add(email)
    db.flush()
    seen_attachments = set()
    for attachment in [*parsed.attachments, *(extra_attachments or [])]:
        digest = hashlib.sha256(attachment.content).hexdigest()
        if digest not in seen_attachments:
            _store_attachment(db, email, attachment)
            seen_attachments.add(digest)
    audit(
        db,
        user.organization_id,
        user.id,
        "EMAIL_INGESTED",
        "procurement_email",
        email.id,
        new={
            "source_type": source_type,
            "message_id": parsed.message_id,
            "attachment_count": len(parsed.attachments) + len(extra_attachments or []),
        },
    )
    db.commit()
    return email


def _store_attachment(db, email: ProcurementEmail, parsed: ParsedAttachment) -> EmailAttachment:
    filename = _safe_filename(parsed.filename)
    content = parsed.content
    digest = hashlib.sha256(content).hexdigest()
    suffix = Path(filename).suffix.casefold()
    supported = suffix in SUPPORTED_ATTACHMENTS
    attachment = EmailAttachment(
        organization_id=email.organization_id,
        email_id=email.id,
        filename=filename,
        content_type=(parsed.content_type or "application/octet-stream")[:200],
        size=len(content),
        sha256=digest,
        storage_path="",
        supported=supported,
        status=("RECEIVED" if supported else "UNSUPPORTED_ATTACHMENT_FOR_CURRENT_PHASE"),
        error=(
            "Scanned PDF and image layout work is deferred in Phase 2.8."
            if suffix in DEFERRED_ATTACHMENTS
            else None if supported else "This attachment type is not supported in Phase 2.8."
        ),
    )
    db.add(attachment)
    db.flush()
    attachment.storage_path = LocalStorageProvider().save(
        email.organization_id, f"email/{email.id}/{attachment.id}{suffix or '.bin'}", content
    )
    duplicate_document = db.scalar(
        select(Document).where(Document.organization_id == email.organization_id, Document.sha256 == digest)
    )
    if duplicate_document:
        attachment.document_id = duplicate_document.id
        attachment.status = "LINKED_DUPLICATE" if supported else attachment.status
        attachment.processed = supported and duplicate_document.processed_at is not None
    return attachment


def _sender_role(db, email: ProcurementEmail) -> str:
    if not email.sender_email:
        return "UNKNOWN"
    user = db.scalar(
        select(User).where(
            User.organization_id == email.organization_id,
            func.lower(User.email) == email.sender_email.casefold(),
        )
    )
    return "BUYER" if user else "SUPPLIER"


def _supplier(db, email: ProcurementEmail, parsed: ParsedEmail, attachment_candidates: list[dict]):
    if email.sender_role != "SUPPLIER":
        return None, "SENDER_NOT_SUPPLIER"
    attachment_name = next((c.get("supplier_name") for c in attachment_candidates if c.get("supplier_name")), None)
    identity_name = supplier_name_from_identity(parsed.sender_name, parsed.signature, parsed.sender_domain) or attachment_name
    result = match_supplier_email(
        db,
        email.organization_id,
        email=email.sender_email,
        domain=email.sender_domain,
        name=identity_name or attachment_name,
    )
    if result.supplier:
        supplier = result.supplier
        if email.sender_email and not db.scalar(
            select(SupplierContact).where(
                SupplierContact.organization_id == email.organization_id,
                SupplierContact.normalized_email == normalized_email(email.sender_email),
            )
        ):
            # Exact company domain or identity evidence can add a contact, while
            # the existing primary contact remains unchanged.
            if result.method in {"EXACT_VERIFIED_DOMAIN", "KNOWN_ALIAS", "NORMALIZED_NAME"}:
                db.add(
                    SupplierContact(
                        organization_id=email.organization_id,
                        supplier_id=supplier.id,
                        name=parsed.sender_name or "Email contact",
                        email=email.sender_email,
                        normalized_email=normalized_email(email.sender_email),
                        created_from_email_id=email.id,
                        auto_created=True,
                    )
                )
        return supplier, result.method
    if result.candidates:
        for candidate, score in result.candidates:
            db.add(
                SupplierMatchCandidate(
                    organization_id=email.organization_id,
                    email_id=email.id,
                    supplier_id=candidate.id,
                    incoming_name=identity_name or attachment_name or parsed.sender_name or email.sender_email,
                    match_method="POSSIBLE_EXISTING_SUPPLIER",
                    score=score,
                )
            )
        return None, "POSSIBLE_EXISTING_SUPPLIER"
    # A personal display name on a generic provider is insufficient company
    # identity. Preserve the email and request review instead of inventing one.
    if not identity_name or (
        email.sender_domain in GENERIC_DOMAINS
        and normalized_supplier_name(identity_name) == normalized_supplier_name(parsed.sender_name)
        and not re.search(r"\b(?:supply|industrial|company|corp|inc|llc|ltd|components|automation)\b", identity_name, re.I)
    ):
        return None, "SUPPLIER_IDENTITY_REVIEW_REQUIRED"
    supplier = Supplier(
        organization_id=email.organization_id,
        name=identity_name[:300],
        normalized_name=normalized_supplier_name(identity_name),
        aliases=[],
        category="Uncategorized",
        status="NEW_UNVERIFIED",
        email_domain=email.sender_domain if email.sender_domain not in GENERIC_DOMAINS else "",
        website="",
        currency="USD",
        payment_terms="Net 30",
        preferred_supplier=False,
        primary_email=email.sender_email or None,
        created_source="EMAIL_INTAKE",
        created_from_email_id=email.id,
        auto_created=True,
    )
    db.add(supplier)
    db.flush()
    if email.sender_email:
        db.add(
            SupplierContact(
                organization_id=email.organization_id,
                supplier_id=supplier.id,
                name=parsed.sender_name or "Email contact",
                email=email.sender_email,
                normalized_email=normalized_email(email.sender_email),
                created_from_email_id=email.id,
                auto_created=True,
            )
        )
    audit(
        db,
        email.organization_id,
        email.ingested_by,
        "SUPPLIER_AUTO_CREATED",
        "supplier",
        supplier.id,
        new={"name": supplier.name, "status": supplier.status, "source_email_id": email.id},
    )
    return supplier, "NEW_UNVERIFIED_CREATED"


def _parsed_from_record(email: ProcurementEmail) -> ParsedEmail:
    _, tables = html_content(email.body_html) if email.body_html else ("", [])
    return ParsedEmail(
        sender_name=email.sender_name,
        sender_email=email.sender_email,
        recipients=email.recipient_emails,
        cc=email.cc_emails,
        subject=email.subject,
        normalized_subject=email.normalized_subject,
        sent_at=email.sent_at,
        message_id=email.message_id,
        in_reply_to=email.in_reply_to,
        references=email.references,
        body_text=email.body_text,
        body_html=email.body_html,
        normalized_body=email.normalized_body,
        quoted_history=email.quoted_history,
        signature=email.signature,
        html_tables=tables,
        content_hash=email.content_hash,
    )


def _context(email: ProcurementEmail, source_type: str, attachment=None, document=None) -> SourceContext:
    return SourceContext(
        source_type=source_type,
        email_id=email.id,
        message_id=email.message_id,
        sent_at=email.sent_at,
        sender=email.sender_email,
        subject=email.subject,
        attachment_id=attachment.id if attachment else None,
        document_id=document.id if document else None,
    )


def _document_for_attachment(db, email: ProcurementEmail, attachment: EmailAttachment) -> Document:
    if attachment.document_id:
        document = db.scalar(
            select(Document).where(
                Document.id == attachment.document_id,
                Document.organization_id == email.organization_id,
            )
        )
        if document:
            return document
    document = Document(
        organization_id=email.organization_id,
        filename=attachment.filename,
        storage_key=attachment.storage_path,
        mime_type=attachment.content_type,
        sha256=attachment.sha256,
        size=attachment.size,
        status="Processing",
        stage="Email Attachment",
        classification="Email Attachment",
        uploaded_by=email.ingested_by,
        rfq_id=email.rfq_id,
    )
    db.add(document)
    db.flush()
    attachment.document_id = document.id
    return document


def _merge_semantic(base: dict, semantic: dict) -> dict:
    result = copy.deepcopy(base)
    result.setdefault("source_references", {})
    for field, value in semantic.items():
        if field in {"line_items", "source_references"}:
            continue
        if result.get(field) is None and value is not None:
            result[field] = value
            if field in semantic.get("source_references", {}):
                result["source_references"][field] = semantic["source_references"][field]
    if not result.get("line_items"):
        result["line_items"] = semantic.get("line_items", [])
    return result


def _qwen_candidate(text: str, sha: str, context: SourceContext, document_input=None) -> dict | None:
    if os.getenv("AI_MODE", "demo") != "local" or os.getenv("EMAIL_USE_QWEN", "true").lower() != "true":
        return None
    try:
        diagnostics = {}
        extraction, _ = extract_quote(text, sha, document_input or DocumentInput(text), diagnostics, allow_fallback=False)
        candidate = extraction.model_dump(mode="python")
        for value in [candidate, *candidate.get("line_items", [])]:
            for evidence in value.get("source_references", {}).values():
                evidence.update(
                    email_id=context.email_id,
                    message_id=context.message_id,
                    sent_at=context.sent_at,
                    sender=context.sender,
                    subject=context.subject,
                    source_type=context.source_type,
                    attachment_id=context.attachment_id,
                    document_id=context.document_id,
                )
        return candidate
    except ValueError:
        return None


def _attachment_candidates(db, email: ProcurementEmail) -> tuple[list[dict], list[str]]:
    candidates, source_texts = [], []
    attachments = db.scalars(
        select(EmailAttachment).where(
            EmailAttachment.organization_id == email.organization_id,
            EmailAttachment.email_id == email.id,
        )
    ).all()
    for attachment in attachments:
        if not attachment.supported:
            audit(
                db,
                email.organization_id,
                email.ingested_by,
                "ATTACHMENT_DEFERRED",
                "email_attachment",
                attachment.id,
                details={"status": attachment.status, "filename": attachment.filename},
            )
            continue
        try:
            path = LocalStorageProvider().path(attachment.storage_path)
            if path.suffix.casefold() == ".pdf":
                reader = PdfReader(path)
                if reader.is_encrypted or sum(len((page.extract_text() or "").strip()) for page in reader.pages) < 80:
                    attachment.supported = False
                    attachment.status = "UNSUPPORTED_ATTACHMENT_FOR_CURRENT_PHASE"
                    attachment.error = "Scanned or image-only PDF processing is deferred in Phase 2.8."
                    continue
            document = _document_for_attachment(db, email, attachment)
            prepared = prepare_document(path)
            document.raw_text = prepared.text[:200000]
            document.status = "Needs Review"
            document.stage = "Attachment Parsed"
            document.processed_at = datetime.now(timezone.utc)
            context = _context(email, "ATTACHMENT", attachment, document)
            candidate = extract_candidate(
                prepared.text,
                context=context,
                structured_rows=prepared.structured_rows,
                sender_role=email.sender_role,
            )
            if not candidate_has_quote(candidate):
                semantic = _qwen_candidate(prepared.text, attachment.sha256, context, prepared)
                if semantic:
                    candidate = _merge_semantic(candidate, semantic)
            candidates.append(candidate)
            source_texts.append(prepared.text)
            attachment.processed = True
            attachment.status = "PROCESSED"
            audit(
                db,
                email.organization_id,
                email.ingested_by,
                "ATTACHMENT_PROCESSED",
                "email_attachment",
                attachment.id,
                details={"document_id": document.id, "filename": attachment.filename},
            )
        except Exception as error:
            attachment.status = "FAILED"
            attachment.error = str(error)[:1000]
            attachment.processed = False
    return candidates, source_texts


def _resolve_thread(db, email: ProcurementEmail) -> EmailThread:
    reference_ids = [value for value in [email.in_reply_to, *email.references] if value]
    referenced = None
    if reference_ids:
        referenced = db.scalar(
            select(ProcurementEmail).where(
                ProcurementEmail.organization_id == email.organization_id,
                ProcurementEmail.message_id.in_(reference_ids),
                ProcurementEmail.thread_id.is_not(None),
            )
        )
    thread = db.get(EmailThread, referenced.thread_id) if referenced else None
    if thread is None and (email.supplier_id or email.rfq_id):
        threshold = (email.sent_at or datetime.now(timezone.utc)) - timedelta(days=30)
        statement = select(EmailThread).where(
            EmailThread.organization_id == email.organization_id,
            EmailThread.normalized_subject == email.normalized_subject,
            EmailThread.last_message_at >= threshold,
        )
        if email.supplier_id:
            statement = statement.where(EmailThread.supplier_id == email.supplier_id)
        if email.rfq_id:
            statement = statement.where(EmailThread.rfq_id == email.rfq_id)
        rows = db.scalars(statement.order_by(EmailThread.last_message_at.desc())).all()
        thread = rows[0] if len(rows) == 1 else None
    if thread is None:
        thread = EmailThread(
            organization_id=email.organization_id,
            subject=email.subject,
            normalized_subject=email.normalized_subject,
            supplier_id=email.supplier_id,
            rfq_id=email.rfq_id,
            last_message_at=email.sent_at or email.created_at,
        )
        db.add(thread)
        db.flush()
    else:
        thread.supplier_id = thread.supplier_id or email.supplier_id
        thread.rfq_id = thread.rfq_id or email.rfq_id
        thread.last_message_at = max(
            [value for value in (thread.last_message_at, email.sent_at, email.created_at) if value],
            key=lambda value: value.replace(tzinfo=None),
        )
    email.thread_id = thread.id
    return thread


def _email_document(db, email: ProcurementEmail) -> Document:
    content = (
        f"From: {email.sender_name} <{email.sender_email}>\nSubject: {email.subject}\n\n{email.normalized_body}"
    ).encode("utf-8")
    digest = hashlib.sha256(email.id.encode() + b"\0" + content).hexdigest()
    key = LocalStorageProvider().save(email.organization_id, f"email/{email.id}/message.txt", content)
    document = Document(
        organization_id=email.organization_id,
        filename=(re.sub(r"[^A-Za-z0-9._ -]", "_", email.subject)[:180] or "email") + ".txt",
        storage_key=key,
        mime_type="text/plain",
        sha256=digest,
        size=len(content),
        status="Needs Review",
        stage="Email Reconciled",
        classification="Supplier Email",
        raw_text=email.normalized_body,
        rfq_id=email.rfq_id,
        uploaded_by=email.ingested_by,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.flush()
    return document


def _store_email_evidence(db, email: ProcurementEmail, extraction):
    def add(field, value, evidence):
        if not evidence or evidence.get("source_type") not in {"EMAIL_BODY", "EMAIL_TABLE", "EMAIL_HEADER", "SIGNATURE", "ATTACHMENT"}:
            return
        db.add(
            EmailEvidence(
                organization_id=email.organization_id,
                email_id=email.id,
                field=field,
                value={"value": str(value) if value is not None else None},
                source_type=evidence.get("source_type"),
                source_snippet=evidence.get("source_text", "")[:4000],
                message_id=email.message_id,
                source_timestamp=email.sent_at,
                attachment_id=evidence.get("attachment_id"),
                decision_status=evidence.get("decision_status", "ACCEPTED"),
                reason=evidence.get("reason"),
            )
        )

    payload = extraction.model_dump(mode="python")
    for field, evidence in payload.get("source_references", {}).items():
        add(field, payload.get(field), evidence)
    for index, line in enumerate(payload.get("line_items", [])):
        for field, evidence in line.get("source_references", {}).items():
            add(f"line_items.{index}.{field}", line.get(field), evidence)


def _quote_snapshot(extraction) -> dict:
    return extraction.model_dump(mode="json")


def _apply_quote(db, email: ProcurementEmail, thread: EmailThread, extraction, document: Document, needs_review: bool):
    prior_email = db.scalar(
        select(ProcurementEmail)
        .where(
            ProcurementEmail.organization_id == email.organization_id,
            ProcurementEmail.thread_id == thread.id,
            ProcurementEmail.quote_id.is_not(None),
            ProcurementEmail.id != email.id,
        )
        .order_by(ProcurementEmail.sent_at.desc(), ProcurementEmail.created_at.desc())
    )
    quote = db.get(Quote, prior_email.quote_id) if prior_email else None
    if quote is None:
        document.rfq_id = email.rfq_id
        extraction.rfq_number = extraction.rfq_number or (
            db.get(RFQ, email.rfq_id).number if email.rfq_id else None
        )
        quote = persist_extraction(
            db,
            document,
            extraction,
            "email-local",
            diagnostics={
                "pipeline_version": PIPELINE_VERSION,
                "prompt_version": PROMPT_VERSION,
                "source": "EMAIL_INTAKE",
                "needs_review": needs_review,
            },
        )
        quote.supplier_id = email.supplier_id
        quote.rfq_id = email.rfq_id
        quote.review_status = "Needs Review"
        revision_number = 1
        previous_revision = None
        action = "QUOTE_CREATED_FROM_EMAIL"
    else:
        previous_revision = db.scalar(
            select(QuoteRevision)
            .where(
                QuoteRevision.organization_id == email.organization_id,
                QuoteRevision.quote_id == quote.id,
                QuoteRevision.effective.is_(True),
            )
            .order_by(QuoteRevision.revision_number.desc())
        )
        if previous_revision:
            previous_revision.effective = False
        revision_number = (previous_revision.revision_number if previous_revision else quote.version) + 1
        values = extraction.model_dump(exclude={"line_items", "source_references"})
        for field, value in values.items():
            setattr(quote, field, value)
        quote.source_references = extraction.model_dump(mode="json")["source_references"]
        quote.supplier_id = email.supplier_id or quote.supplier_id
        quote.rfq_id = email.rfq_id or quote.rfq_id
        quote.review_status = "Needs Review"
        quote.version += 1
        existing = db.scalars(
            select(QuoteItem).where(
                QuoteItem.organization_id == email.organization_id,
                QuoteItem.quote_id == quote.id,
            )
        ).all()
        by_sku = {str(item.supplier_sku or "").casefold(): item for item in existing}
        used = set()
        for line in extraction.line_items:
            record = by_sku.get(str(line.supplier_sku or "").casefold())
            if record is None and len(existing) == 1 and len(extraction.line_items) == 1:
                record = existing[0]
            item, method, _ = match_item(
                db,
                email.organization_id,
                quote.supplier_id,
                line.supplier_sku,
                line.manufacturer_part_number,
                line.description,
            )
            values = line.model_dump(exclude={"source_references", "price_tiers"})
            if record is None:
                record = QuoteItem(
                    organization_id=email.organization_id,
                    quote_id=quote.id,
                    item_id=item.id if item else None,
                    match_method=method,
                    **values,
                )
                db.add(record)
            else:
                for field, value in values.items():
                    setattr(record, field, value)
                record.item_id = item.id if item else record.item_id
                record.match_method = method
            record.source_references = line.model_dump(mode="json")["source_references"]
            record.price_tiers = line.model_dump(mode="json")["price_tiers"]
            used.add(record.id)
        for record in existing:
            if record.id not in used:
                db.delete(record)
        if quote.rfq_id:
            rfq = db.scalar(
                select(RFQ).where(RFQ.id == quote.rfq_id, RFQ.organization_id == email.organization_id).with_for_update()
            )
            if rfq:
                invalidate(db, rfq)
                refresh_alerts(db, email.organization_id, rfq, email.ingested_by)
        action = "QUOTE_REVISION_CREATED"
    revision = QuoteRevision(
        organization_id=email.organization_id,
        quote_id=quote.id,
        revision_number=revision_number,
        email_id=email.id,
        document_id=document.id,
        source_timestamp=email.sent_at,
        reason=email.email_type,
        supersedes_revision_id=previous_revision.id if previous_revision else None,
        snapshot=_quote_snapshot(extraction),
        effective=True,
    )
    db.add(revision)
    email.quote_id = quote.id
    audit(
        db,
        email.organization_id,
        email.ingested_by,
        action,
        "quote",
        quote.id,
        details={"email_id": email.id, "revision_number": revision_number},
    )
    return quote


def process_email(email_id: str, organization_id: str):
    with SessionLocal() as db:
        email = db.scalar(
            select(ProcurementEmail)
            .where(ProcurementEmail.id == email_id, ProcurementEmail.organization_id == organization_id)
            .with_for_update()
        )
        if not email or email.status == "COMPLETE":
            return
        started = time.monotonic()
        try:
            email.status = "PARSING"
            db.commit()
            parsed = _parsed_from_record(email)
            email.email_type = classify_email(email.subject, email.normalized_body)
            email.sender_role = _sender_role(db, email)
            email.status = "PROCESSING_ATTACHMENTS"
            db.commit()
            attachment_candidates, attachment_texts = _attachment_candidates(db, email)
            email.status = "MATCHING_SUPPLIER"
            supplier, supplier_method = _supplier(db, email, parsed, attachment_candidates)
            email.supplier_id = supplier.id if supplier else None
            if supplier:
                audit(
                    db,
                    email.organization_id,
                    email.ingested_by,
                    "SUPPLIER_MATCHED",
                    "procurement_email",
                    email.id,
                    new={"supplier_id": supplier.id, "method": supplier_method},
                )
            elif supplier_method == "POSSIBLE_EXISTING_SUPPLIER":
                audit(
                    db,
                    email.organization_id,
                    email.ingested_by,
                    "SUPPLIER_MATCH_REVIEW_REQUIRED",
                    "procurement_email",
                    email.id,
                    details={"method": supplier_method},
                )
            rfq, rfq_method = match_rfq(
                db,
                email.organization_id,
                email.subject,
                email.normalized_body,
                *attachment_texts,
                explicit_id=email.rfq_id,
            )
            email.rfq_id = rfq.id if rfq else None
            if rfq:
                audit(
                    db,
                    email.organization_id,
                    email.ingested_by,
                    "RFQ_MATCHED",
                    "procurement_email",
                    email.id,
                    new={"rfq_id": rfq.id, "method": rfq_method},
                )
            thread = _resolve_thread(db, email)
            context = _context(email, "EMAIL_TABLE" if parsed.html_tables else "EMAIL_BODY")
            candidate = extract_candidate(
                email.normalized_body,
                context=context,
                supplier_name=supplier.name if supplier else supplier_name_from_identity(
                    email.sender_name, email.signature, email.sender_domain
                ),
                sender_role=email.sender_role,
                tables=parsed.html_tables,
            )
            if email.sender_role == "SUPPLIER" and not candidate_has_quote(candidate):
                semantic = _qwen_candidate(email.normalized_body, email.content_hash, context)
                if semantic:
                    candidate = _merge_semantic(candidate, semantic)
            email.status = "RECONCILING"
            result = reconcile_candidates(candidate, attachment_candidates, email.normalized_body)
            review_reasons = []
            if not email.sender_email:
                review_reasons.append("Missing From header")
            if supplier is None:
                review_reasons.append(supplier_method)
            if rfq is None:
                review_reasons.append(rfq_method)
            if email.email_type not in {"QUOTE", "QUOTE_REVISION", "RFQ_RESPONSE", "NEGOTIATION"}:
                review_reasons.append("Email is not a supported quote workflow type")
            if result.extraction is None:
                review_reasons.append("No evidence-backed supplier quote fields found")
            for conflict in result.conflicts:
                db.add(
                    EmailFieldConflict(
                        organization_id=email.organization_id,
                        email_id=email.id,
                        field=conflict.field,
                        email_value={"value": str(conflict.email_value)},
                        attachment_value={"value": str(conflict.attachment_value)},
                        attachment_id=conflict.attachment_id,
                        resolution=conflict.resolution,
                        reason=conflict.reason,
                    )
                )
                audit(
                    db,
                    email.organization_id,
                    email.ingested_by,
                    "FIELD_CONFLICT_DETECTED",
                    "procurement_email",
                    email.id,
                    details={"field": conflict.field, "resolution": conflict.resolution},
                )
            if result.extraction and email.sender_role == "SUPPLIER" and email.email_type in {
                "QUOTE",
                "QUOTE_REVISION",
                "RFQ_RESPONSE",
                "NEGOTIATION",
            }:
                result.extraction.supplier_name = supplier.name if supplier else result.extraction.supplier_name
                result.extraction.supplier_email = email.sender_email or result.extraction.supplier_email
                result.extraction.rfq_number = rfq.number if rfq else result.extraction.rfq_number
                document = _email_document(db, email)
                quote = _apply_quote(db, email, thread, result.extraction, document, result.needs_review or bool(review_reasons))
                _store_email_evidence(db, email, result.extraction)
                document.status = "Needs Review"
                document.stage = "Email Review Required" if result.needs_review or review_reasons else "Email Complete"
                quote.review_status = "Needs Review"
            email.processing_metrics = {
                "pipeline_version": PIPELINE_VERSION,
                "prompt_version": PROMPT_VERSION,
                "total_seconds": round(time.monotonic() - started, 4),
                "attachment_count": len(attachment_candidates),
                "sources_used": result.sources_used,
            }
            if review_reasons or result.needs_review:
                email.status = "NEEDS_REVIEW"
                email.status_reason = "; ".join(dict.fromkeys(review_reasons)) or "Field conflict requires review."
            else:
                email.status = "COMPLETE"
                email.status_reason = None
            db.commit()
        except Exception as error:
            db.rollback()
            email = db.scalar(
                select(ProcurementEmail).where(
                    ProcurementEmail.id == email_id, ProcurementEmail.organization_id == organization_id
                )
            )
            if email:
                email.status = "FAILED"
                email.status_reason = "Email processing failed; the source remains stored for retry or review."
                email.processing_metrics = {
                    "pipeline_version": PIPELINE_VERSION,
                    "error_type": type(error).__name__,
                    "total_seconds": round(time.monotonic() - started, 4),
                }
                audit(
                    db,
                    organization_id,
                    email.ingested_by,
                    "EMAIL_PROCESSING_FAILED",
                    "procurement_email",
                    email.id,
                    details={"error_type": type(error).__name__},
                )
                db.commit()
            log.exception("email_processing_failed", extra={"email_id": email_id})


def retry_email(email_id: str, organization_id: str):
    with SessionLocal() as db:
        email = db.scalar(
            select(ProcurementEmail).where(
                ProcurementEmail.id == email_id, ProcurementEmail.organization_id == organization_id
            )
        )
        if email and email.status in {"FAILED", "NEEDS_REVIEW"} and email.quote_id is None:
            email.status = "RECEIVED"
            email.status_reason = None
            db.commit()
    process_email(email_id, organization_id)


def email_detail(db, email: ProcurementEmail) -> dict:
    attachments = db.scalars(
        select(EmailAttachment).where(
            EmailAttachment.organization_id == email.organization_id,
            EmailAttachment.email_id == email.id,
        )
    ).all()
    evidence = db.scalars(
        select(EmailEvidence).where(
            EmailEvidence.organization_id == email.organization_id,
            EmailEvidence.email_id == email.id,
        )
    ).all()
    conflicts = db.scalars(
        select(EmailFieldConflict).where(
            EmailFieldConflict.organization_id == email.organization_id,
            EmailFieldConflict.email_id == email.id,
        )
    ).all()
    candidates = db.scalars(
        select(SupplierMatchCandidate).where(
            SupplierMatchCandidate.organization_id == email.organization_id,
            SupplierMatchCandidate.email_id == email.id,
        )
    ).all()
    timeline = []
    if email.thread_id:
        timeline = [
            {
                "email_id": row.id,
                "sent_at": row.sent_at,
                "sender": row.sender_email,
                "type": row.email_type,
                "subject": row.subject,
                "status": row.status,
                "quote_id": row.quote_id,
            }
            for row in db.scalars(
                select(ProcurementEmail)
                .where(
                    ProcurementEmail.organization_id == email.organization_id,
                    ProcurementEmail.thread_id == email.thread_id,
                )
                .order_by(ProcurementEmail.sent_at, ProcurementEmail.created_at)
            )
        ]
    supplier = db.get(Supplier, email.supplier_id) if email.supplier_id else None
    rfq = db.get(RFQ, email.rfq_id) if email.rfq_id else None
    return {
        **serialize(email),
        "supplier": serialize(supplier) if supplier else None,
        "rfq": serialize(rfq) if rfq else None,
        "attachments": [serialize(row) for row in attachments],
        "evidence": [serialize(row) for row in evidence],
        "conflicts": [serialize(row) for row in conflicts],
        "supplier_candidates": [serialize(row) for row in candidates],
        "timeline": timeline,
    }
