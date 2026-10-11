from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select

from app.email_intake import persist_email, process_email
from app.email_parser import ParsedAttachment, parse_pasted
from app.models import (
    EmailAttachment,
    EmailFieldConflict,
    ProcurementEmail,
    Quote,
    QuoteItem,
    QuoteRevision,
    Supplier,
    SupplierContact,
)
from app.seed import sid


def _process(db_factory, monkeypatch, parsed, attachments=None):
    monkeypatch.setattr("app.email_intake.SessionLocal", db_factory)
    with db_factory() as db:
        user = db.get(__import__("app.models", fromlist=["User"]).User, sid("Buyer"))
        email = persist_email(db, user, parsed, "TEST", extra_attachments=attachments)
        email_id = email.id
        organization_id = email.organization_id
    process_email(email_id, organization_id)
    with db_factory() as db:
        return db.get(ProcurementEmail, email_id)


def test_exact_email_supplier_rfq_quote_and_evidence(db_factory, monkeypatch):
    parsed = parse_pasted(
        sender="Atlas Quotes <sales@atlas.example>",
        subject="Quote #ATL-1003 for RFQ-1003",
        sent_at=datetime(2026, 9, 14, 17, tzinfo=timezone.utc),
        message_id="<atlas-first@example>",
        body_text="Prices USD\nAX-100: Qty 5000 Unit price $4.48\nLead time: 3 weeks\nTerms: Net 30",
    )
    email = _process(db_factory, monkeypatch, parsed)
    assert email.status == "COMPLETE"
    assert email.supplier_id == sid("supplier-0")
    assert email.rfq_id == sid("rfq-3")
    with db_factory() as db:
        quote = db.get(Quote, email.quote_id)
        line = db.scalar(select(QuoteItem).where(QuoteItem.quote_id == quote.id))
        assert quote.quote_number == "ATL-1003"
        assert quote.currency == "USD"
        assert line.quantity == 5000
        assert line.unit_price == Decimal("4.48")
        assert line.lead_time_days == 21
        assert db.scalar(select(QuoteRevision).where(QuoteRevision.quote_id == quote.id)).revision_number == 1


def test_new_supplier_is_unverified_with_provenance_and_contact(db_factory, monkeypatch):
    parsed = parse_pasted(
        sender="Jamie Lee <quotes@redwoodmotion.com>",
        subject="RFQ 1003 Quote RWM-18",
        sent_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        message_id="<redwood@example>",
        body_text="AX-100 Qty: 5000 Unit Price: 4.48 USD\nRegards,\nJamie Lee\nRedwood Motion Components LLC",
    )
    email = _process(db_factory, monkeypatch, parsed)
    with db_factory() as db:
        supplier = db.get(Supplier, email.supplier_id)
        contact = db.scalar(select(SupplierContact).where(SupplierContact.supplier_id == supplier.id))
        assert supplier.status == "NEW_UNVERIFIED"
        assert supplier.created_source == "EMAIL_INTAKE"
        assert supplier.created_from_email_id == email.id
        assert supplier.auto_created
        assert contact.normalized_email == "quotes@redwoodmotion.com"


def test_possible_duplicate_does_not_auto_link_or_create(db_factory, monkeypatch):
    parsed = parse_pasted(
        sender="Atlas Team <quotes@gmail.com>",
        subject="RFQ-1003 quotation",
        message_id="<atlas-fuzzy@example>",
        body_text="AX-100 Qty: 5000 Unit Price: 4.48 USD\nRegards,\nAtlas Industrial Supplies LLC",
    )
    before = None
    with db_factory() as db:
        before = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(Supplier))
    email = _process(db_factory, monkeypatch, parsed)
    with db_factory() as db:
        after = db.scalar(select(__import__("sqlalchemy").func.count()).select_from(Supplier))
        assert email.supplier_id is None
        assert email.status == "NEEDS_REVIEW"
        assert before == after
        assert email.status_reason and "POSSIBLE_EXISTING_SUPPLIER" in email.status_reason


def test_revision_updates_effective_quote_and_preserves_snapshot(db_factory, monkeypatch):
    first = parse_pasted(
        sender="sales@atlas.example",
        subject="RFQ-1003 Quote ATL-REV",
        sent_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        message_id="<rev-1@example>",
        body_text="AX-100 Qty: 5000 Unit Price: 4.72 USD",
    )
    first_email = _process(db_factory, monkeypatch, first)
    second = parse_pasted(
        sender="sales@atlas.example",
        subject="RE: RFQ-1003 Revised Quote ATL-REV",
        sent_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
        message_id="<rev-2@example>",
        in_reply_to="<rev-1@example>",
        references=["<rev-1@example>"],
        body_text="Updated pricing\nAX-100 Qty: 5000 Unit Price: 4.48 USD",
    )
    second_email = _process(db_factory, monkeypatch, second)
    assert second_email.thread_id == first_email.thread_id
    assert second_email.quote_id == first_email.quote_id
    with db_factory() as db:
        quote = db.get(Quote, second_email.quote_id)
        line = db.scalar(select(QuoteItem).where(QuoteItem.quote_id == quote.id))
        revisions = db.scalars(
            select(QuoteRevision).where(QuoteRevision.quote_id == quote.id).order_by(QuoteRevision.revision_number)
        ).all()
        assert line.unit_price == Decimal("4.48")
        assert [row.effective for row in revisions] == [False, True]
        assert revisions[0].snapshot["line_items"][0]["unit_price"] == "4.72"


def test_csv_and_xlsx_attachments_merge_with_email(db_factory, monkeypatch):
    csv_attachment = ParsedAttachment(
        "quote.csv",
        "text/csv",
        b"SKU,Qty,Unit Price,MOQ\nAX-100,5000,4.48,500\n",
    )
    book = Workbook()
    sheet = book.active
    sheet.append(["SKU", "Qty", "Unit Price"])
    sheet.append(["BX-220", 1000, 46.58])
    stream = BytesIO()
    book.save(stream)
    xlsx_attachment = ParsedAttachment(
        "quote.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        stream.getvalue(),
    )
    parsed = parse_pasted(
        sender="sales@atlas.example",
        subject="RFQ-1003 Quote ATL-ATT",
        message_id="<attachments@example>",
        body_text="Terms: Net 30\nLead time: 21 days\nCurrency: USD",
    )
    email = _process(db_factory, monkeypatch, parsed, [csv_attachment, xlsx_attachment])
    with db_factory() as db:
        attachments = db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == email.id)).all()
        lines = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == email.quote_id)).all()
        assert all(row.processed for row in attachments)
        assert {row.supplier_sku for row in lines} == {"AX-100", "BX-220"}


def test_attachment_conflict_requires_review(db_factory, monkeypatch):
    parsed = parse_pasted(
        sender="sales@atlas.example",
        subject="RFQ-1003 Quote conflict",
        message_id="<conflict@example>",
        body_text="AX-100 Qty: 5000 Unit Price: 4.60 USD",
    )
    attachment = ParsedAttachment("quote.csv", "text/csv", b"SKU,Qty,Unit Price\nAX-100,5000,4.48\n")
    email = _process(db_factory, monkeypatch, parsed, [attachment])
    assert email.status == "NEEDS_REVIEW"
    with db_factory() as db:
        conflict = db.scalar(select(EmailFieldConflict).where(EmailFieldConflict.email_id == email.id))
        assert conflict.resolution == "REVIEW_REQUIRED"


def test_image_attachment_is_stored_and_deferred(db_factory, monkeypatch):
    parsed = parse_pasted(
        sender="sales@atlas.example",
        subject="RFQ-1003 Quote image",
        message_id="<image@example>",
        body_text="AX-100 Qty: 5000 Unit Price: 4.48 USD",
    )
    image = ParsedAttachment("scan.png", "image/png", b"not decoded because phase is deferred")
    email = _process(db_factory, monkeypatch, parsed, [image])
    with db_factory() as db:
        attachment = db.scalar(select(EmailAttachment).where(EmailAttachment.email_id == email.id))
        assert attachment.status == "UNSUPPORTED_ATTACHMENT_FOR_CURRENT_PHASE"
        assert not attachment.supported


def test_duplicate_message_id_and_cross_tenant_api_isolation(buyer, client, db_factory, monkeypatch):
    payload = {
        "sender": "sales@atlas.example",
        "subject": "RFQ-1003 Quote duplicate",
        "message_id": "<duplicate@example>",
        "body_text": "AX-100 Qty: 5000 Unit Price: 4.48 USD",
    }
    first = buyer.post("/emails/paste", json=payload)
    second = buyer.post("/emails/paste", json=payload)
    assert first.status_code == second.status_code == 202
    assert second.json()["duplicate"] is True
    email_id = first.json()["id"]
    client.post("/auth/login", json={"email": "viewer@isolated.example", "password": "Demo2026!accord"})
    assert client.get(f"/emails/{email_id}").status_code == 404
    assert client.get("/emails").json()["total"] == 0
