"""Developer utility: freeze the initial schema before its first release."""

from pathlib import Path
from sqlalchemy import create_engine
from alembic.migration import MigrationContext
from alembic.autogenerate import produce_migrations, render_python_code
from app.db import Base
from app import models  # noqa: F401

with create_engine("sqlite://").connect() as connection:
    migration = produce_migrations(MigrationContext.configure(connection), Base.metadata)
up = render_python_code(migration.upgrade_ops)
down = render_python_code(migration.downgrade_ops)
text = (
    '''"""Initial procurement schema, frozen at release 1."""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None

def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
'''
    + up
    + """\n\ndef downgrade():\n"""
    + down
    + "\n"
)
Path("migrations/versions/0001_initial.py").write_text(text, encoding="utf-8")
