"""Local extraction diagnostics, correction lineage, and explicit missing fields."""

from alembic import op
import sqlalchemy as sa

revision = "0002_local_extraction"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_extractions", sa.Column("diagnostics", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("field_corrections", sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"))
    for table, fields in {
        "quotes": ["supplier_name", "quote_number", "currency"],
        "quote_items": ["supplier_sku", "description"],
    }.items():
        with op.batch_alter_table(table) as batch:
            for field in fields:
                batch.alter_column(field, existing_type=sa.String(), nullable=True)


def downgrade():
    # Deliberately refuse lossy downgrade when missing source values exist.
    for table, fields in {
        "quotes": ["supplier_name", "quote_number", "currency"],
        "quote_items": ["supplier_sku", "description"],
    }.items():
        with op.batch_alter_table(table) as batch:
            for field in fields:
                batch.alter_column(field, existing_type=sa.String(), nullable=False)
    op.drop_column("field_corrections", "provenance")
    op.drop_column("document_extractions", "diagnostics")
