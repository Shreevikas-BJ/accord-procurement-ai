"""Create, migrate, seed twice, check and drop only a unique verification database."""

import json
import os
import subprocess
import tempfile
import uuid
from sqlalchemy import create_engine, text
from app.db import engine


def main():
    assert engine.dialect.name == "postgresql"
    name = "accord_verify_" + uuid.uuid4().hex
    admin = engine.execution_options(isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    check_engine = create_engine(engine.url.set(database=name))
    try:
        with tempfile.TemporaryDirectory(prefix="accord-storage-") as storage:
            env = {
                **os.environ,
                "DATABASE_URL": engine.url.set(database=name).render_as_string(hide_password=False),
                "LOCAL_STORAGE_PATH": storage,
            }
            for command in (
                ["alembic", "upgrade", "head"],
                ["python", "-m", "app.seed"],
                ["python", "-m", "app.seed"],
                ["alembic", "check"],
            ):
                subprocess.run(command, env=env, check=True)
            with check_engine.connect() as conn:
                counts = {
                    table: conn.scalar(text(f"SELECT count(*) FROM {table}"))
                    for table in ("suppliers", "items", "purchase_history", "rfqs", "quotes")
                }
                assert list(counts.values()) == [50, 250, 2000, 5, 20], counts
                assert conn.scalar(text("SELECT extname FROM pg_extension WHERE extname='vector'")) == "vector"
                print(
                    json.dumps(
                        {
                            "result": "PASS",
                            "fresh_postgresql": True,
                            "migration": conn.scalar(text("SELECT version_num FROM alembic_version")),
                            "idempotent_seed_counts": counts,
                        }
                    )
                )
    finally:
        check_engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}"'))


if __name__ == "__main__":
    main()
