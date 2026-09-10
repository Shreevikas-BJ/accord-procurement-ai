"""Emit a non-secret fingerprint of persisted business rows and private file bytes."""

import hashlib
import json
from sqlalchemy import select, func
from app.db import Base, SessionLocal, engine
from app.models import Document
from app.providers import LocalStorageProvider


def main():
    assert engine.dialect.name == "postgresql"
    with SessionLocal() as db:
        counts = {
            name: db.scalar(select(func.count()).select_from(table))
            for name, table in sorted(Base.metadata.tables.items())
        }
        files = {}
        for doc in db.scalars(select(Document).order_by(Document.id)):
            path = LocalStorageProvider().path(doc.storage_key)
            assert path.is_file(), f"Missing source for {doc.id}"
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == doc.sha256, f"Source bytes changed for {doc.id}"
            files[doc.id] = digest
        rows = {}
        for name, table in sorted(Base.metadata.tables.items()):
            rows[name] = [
                {key: value for key, value in row.items() if key not in ("password_hash", "token_hash")}
                for row in db.execute(select(table).order_by(table.c.id)).mappings()
            ]
        serialized = json.dumps({"rows": rows, "files": files}, sort_keys=True, default=str)
        print(
            json.dumps(
                {
                    "counts": counts,
                    "verified_source_files": len(files),
                    "fingerprint": hashlib.sha256(serialized.encode()).hexdigest(),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
