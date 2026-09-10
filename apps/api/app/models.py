"""Tenant-owned relational records. JSON is limited to evidence and immutable snapshots."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Text, Date, DateTime, Numeric, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Tenant(Record):
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Organization(Record, Base):
    __tablename__ = "organizations"
    name: Mapped[str]
    currency: Mapped[str] = mapped_column(default="USD")


class User(Tenant, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    password_hash: Mapped[str]
    role: Mapped[str]
    active: Mapped[bool] = mapped_column(default=True)


class AuthSession(Tenant, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Supplier(Tenant, Base):
    __tablename__ = "suppliers"
    name: Mapped[str]
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str]
    status: Mapped[str] = mapped_column(default="Active")
    email_domain: Mapped[str]
    website: Mapped[str] = mapped_column(default="")
    currency: Mapped[str] = mapped_column(default="USD")
    payment_terms: Mapped[str] = mapped_column(default="Net 30")
    preferred_supplier: Mapped[bool] = mapped_column(default=False)


class SupplierContact(Tenant, Base):
    __tablename__ = "supplier_contacts"
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    name: Mapped[str]
    email: Mapped[str]


class Item(Tenant, Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("organization_id", "sku"),)
    sku: Mapped[str]
    manufacturer_part_number: Mapped[str]
    description: Mapped[str]
    category: Mapped[str]
    uom: Mapped[str] = mapped_column(default="EA")
    preferred_supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"))


class ItemAlias(Tenant, Base):
    __tablename__ = "item_aliases"
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    alias: Mapped[str]


class SupplierItemMapping(Tenant, Base):
    __tablename__ = "supplier_item_mappings"
    __table_args__ = (UniqueConstraint("organization_id", "supplier_id", "supplier_sku"),)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    supplier_sku: Mapped[str]
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    confirmed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class RFQ(Tenant, Base):
    __tablename__ = "rfqs"
    __table_args__ = (UniqueConstraint("organization_id", "number"),)
    number: Mapped[str]
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(default="Open")
    required_delivery: Mapped[datetime] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(default="USD")
    supplier_count: Mapped[int] = mapped_column(default=4)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    revision: Mapped[int] = mapped_column(default=1)


class RFQItem(Tenant, Base):
    __tablename__ = "rfq_items"
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))


class Document(Tenant, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("organization_id", "sha256"),)
    filename: Mapped[str]
    storage_key: Mapped[str]
    mime_type: Mapped[str]
    sha256: Mapped[str]
    size: Mapped[int]
    status: Mapped[str] = mapped_column(default="New")
    stage: Mapped[str] = mapped_column(default="Uploading")
    classification: Mapped[str] = mapped_column(default="Unknown")
    error: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    rfq_id: Mapped[str | None] = mapped_column(ForeignKey("rfqs.id"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentExtraction(Tenant, Base):
    __tablename__ = "document_extractions"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    provider: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    diagnostics: Mapped[dict] = mapped_column(JSON, default=dict)


class Quote(Tenant, Base):
    __tablename__ = "quotes"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    rfq_id: Mapped[str | None] = mapped_column(ForeignKey("rfqs.id"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    supplier_name: Mapped[str | None]
    supplier_email: Mapped[str | None]
    quote_number: Mapped[str | None]
    rfq_number: Mapped[str | None]
    quote_date: Mapped[datetime | None] = mapped_column(Date)
    expiration_date: Mapped[datetime | None] = mapped_column(Date)
    currency: Mapped[str | None]
    payment_terms: Mapped[str | None]
    shipping_terms: Mapped[str | None]
    shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    stated_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    stated_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    notes: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1)
    source_references: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(default="Needs Review")
    version: Mapped[int] = mapped_column(default=1)


class QuoteItem(Tenant, Base):
    __tablename__ = "quote_items"
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), index=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("items.id"))
    supplier_sku: Mapped[str | None]
    manufacturer_part_number: Mapped[str | None]
    description: Mapped[str | None]
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    uom: Mapped[str | None]
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    moq: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    lead_time_days: Mapped[int | None]
    lead_time_min: Mapped[int | None]
    delivery_date: Mapped[datetime | None] = mapped_column(Date)
    stated_line_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1)
    match_method: Mapped[str] = mapped_column(default="Unmatched")
    source_references: Mapped[dict] = mapped_column(JSON, default=dict)
    price_tiers: Mapped[list] = mapped_column(JSON, default=list)


class PurchaseHistory(Tenant, Base):
    __tablename__ = "purchase_history"
    __table_args__ = (UniqueConstraint("organization_id", "po_number", "item_id"),)
    po_number: Mapped[str]
    date: Mapped[datetime] = mapped_column(Date, index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(default="USD")
    uom: Mapped[str] = mapped_column(default="EA")
    lead_time_days: Mapped[int]
    expected_delivery: Mapped[datetime] = mapped_column(Date)
    actual_delivery: Mapped[datetime | None] = mapped_column(Date)


class Recommendation(Tenant, Base):
    __tablename__ = "recommendations"
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), index=True)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"))
    revision: Mapped[int]
    explanation: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="Pending Review")


class Alert(Tenant, Base):
    __tablename__ = "alerts"
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), index=True)
    code: Mapped[str]
    message: Mapped[str]
    severity: Mapped[str] = mapped_column(default="warning")


class EmailDraft(Tenant, Base):
    __tablename__ = "email_drafts"
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"))
    kind: Mapped[str]
    subject: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="Draft")


class Approval(Tenant, Base):
    __tablename__ = "approvals"
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"), unique=True)
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(Text)


class AuditEvent(Tenant, Base):
    __tablename__ = "audit_events"
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(index=True)
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class FieldCorrection(Tenant, Base):
    __tablename__ = "field_corrections"
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"))
    field: Mapped[str]
    original_value: Mapped[dict] = mapped_column(JSON)
    corrected_value: Mapped[dict] = mapped_column(JSON)
    corrected_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class ScoringSettings(Tenant, Base):
    __tablename__ = "scoring_settings"
    __table_args__ = (UniqueConstraint("organization_id"),)
    price_weight: Mapped[int] = mapped_column(default=50)
    lead_time_weight: Mapped[int] = mapped_column(default=25)
    reliability_weight: Mapped[int] = mapped_column(default=15)
    fit_weight: Mapped[int] = mapped_column(default=10)
    anomaly_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.10"))
    lead_time_behavior: Mapped[str] = mapped_column(default="conservative")
