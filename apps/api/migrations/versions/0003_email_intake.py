"""Tenant-scoped email intake, supplier provenance, and quote revisions."""

from alembic import op
import sqlalchemy as sa


revision = "0003_email_intake"
down_revision = "0002_local_extraction"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("suppliers", sa.Column("normalized_name", sa.String(), nullable=False, server_default=""))
    op.add_column("suppliers", sa.Column("primary_email", sa.String(), nullable=True))
    op.add_column("suppliers", sa.Column("created_source", sa.String(), nullable=False, server_default="CATALOG"))
    op.add_column("suppliers", sa.Column("created_from_email_id", sa.String(length=36), nullable=True))
    op.add_column("suppliers", sa.Column("auto_created", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_suppliers_normalized_name", "suppliers", ["normalized_name"])
    op.add_column("supplier_contacts", sa.Column("normalized_email", sa.String(), nullable=False, server_default=""))
    op.add_column("supplier_contacts", sa.Column("created_from_email_id", sa.String(length=36), nullable=True))
    op.add_column("supplier_contacts", sa.Column("auto_created", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE suppliers SET normalized_name = lower(regexp_replace(name, '[^a-zA-Z0-9]+', '', 'g'))")
    op.execute("UPDATE supplier_contacts SET normalized_email = lower(email)")
    op.create_index("ix_supplier_contacts_normalized_email", "supplier_contacts", ["normalized_email"])

    op.create_table(
        "email_threads",
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("normalized_subject", sa.String(), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), nullable=True),
        sa.Column("rfq_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for field in ("organization_id", "normalized_subject", "supplier_id", "rfq_id", "last_message_at"):
        op.create_index(f"ix_email_threads_{field}", "email_threads", [field])

    op.create_table(
        "procurement_emails",
        sa.Column("thread_id", sa.String(length=36), nullable=True),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("in_reply_to", sa.String(), nullable=True),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("sender_name", sa.String(), nullable=False),
        sa.Column("sender_email", sa.String(), nullable=False),
        sa.Column("sender_domain", sa.String(), nullable=False),
        sa.Column("recipient_emails", sa.JSON(), nullable=False),
        sa.Column("cc_emails", sa.JSON(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("normalized_subject", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("normalized_body", sa.Text(), nullable=False),
        sa.Column("quoted_history", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("ingested_by", sa.String(length=36), nullable=False),
        sa.Column("email_type", sa.String(), nullable=False, server_default="UNKNOWN"),
        sa.Column("sender_role", sa.String(), nullable=False, server_default="UNKNOWN"),
        sa.Column("supplier_id", sa.String(length=36), nullable=True),
        sa.Column("rfq_id", sa.String(length=36), nullable=True),
        sa.Column("quote_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="RECEIVED"),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("processing_metrics", sa.JSON(), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ingested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["email_threads.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"]),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "message_id", name="uq_procurement_email_org_message_id"),
    )
    for field in (
        "organization_id", "thread_id", "message_id", "content_hash", "normalized_subject", "sent_at",
        "supplier_id", "rfq_id", "quote_id", "status", "ingested_by",
    ):
        op.create_index(f"ix_procurement_emails_{field}", "procurement_emails", [field])

    op.create_table(
        "email_attachments",
        sa.Column("email_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(), nullable=False, server_default="RECEIVED"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["procurement_emails.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "email_id", "sha256", name="uq_email_attachment_org_email_sha"),
    )
    for field in ("organization_id", "email_id", "sha256", "document_id"):
        op.create_index(f"ix_email_attachments_{field}", "email_attachments", [field])

    op.create_table(
        "email_evidence",
        sa.Column("email_id", sa.String(length=36), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_snippet", sa.Text(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attachment_id", sa.String(length=36), nullable=True),
        sa.Column("decision_status", sa.String(), nullable=False, server_default="ACCEPTED"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["procurement_emails.id"]),
        sa.ForeignKeyConstraint(["attachment_id"], ["email_attachments.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for field in ("organization_id", "email_id", "field", "attachment_id"):
        op.create_index(f"ix_email_evidence_{field}", "email_evidence", [field])

    op.create_table(
        "supplier_match_candidates",
        sa.Column("email_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), nullable=False),
        sa.Column("incoming_name", sa.String(), nullable=False),
        sa.Column("match_method", sa.String(), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["procurement_emails.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for field in ("organization_id", "email_id", "supplier_id"):
        op.create_index(f"ix_supplier_match_candidates_{field}", "supplier_match_candidates", [field])

    op.create_table(
        "email_field_conflicts",
        sa.Column("email_id", sa.String(length=36), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("email_value", sa.JSON(), nullable=True),
        sa.Column("attachment_value", sa.JSON(), nullable=True),
        sa.Column("attachment_id", sa.String(length=36), nullable=True),
        sa.Column("resolution", sa.String(), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["procurement_emails.id"]),
        sa.ForeignKeyConstraint(["attachment_id"], ["email_attachments.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for field in ("organization_id", "email_id", "field"):
        op.create_index(f"ix_email_field_conflicts_{field}", "email_field_conflicts", [field])

    op.create_table(
        "quote_revisions",
        sa.Column("quote_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.String(length=36), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("supersedes_revision_id", sa.String(length=36), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("effective", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"]),
        sa.ForeignKeyConstraint(["email_id"], ["procurement_emails.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["supersedes_revision_id"], ["quote_revisions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "quote_id", "revision_number", name="uq_quote_revision_org_number"),
    )
    for field in ("organization_id", "quote_id", "email_id", "document_id"):
        op.create_index(f"ix_quote_revisions_{field}", "quote_revisions", [field])


def downgrade():
    for table in (
        "quote_revisions", "email_field_conflicts", "supplier_match_candidates", "email_evidence",
        "email_attachments", "procurement_emails", "email_threads",
    ):
        op.drop_table(table)
    op.drop_index("ix_supplier_contacts_normalized_email", table_name="supplier_contacts")
    for column in ("auto_created", "created_from_email_id", "normalized_email"):
        op.drop_column("supplier_contacts", column)
    op.drop_index("ix_suppliers_normalized_name", table_name="suppliers")
    for column in ("auto_created", "created_from_email_id", "created_source", "primary_email", "normalized_name"):
        op.drop_column("suppliers", column)
