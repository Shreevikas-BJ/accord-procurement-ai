"""Read-only proof of fresh local evidence acceptance and correction provenance."""

import hashlib
import json
from decimal import Decimal
from sqlalchemy import select, func

from app.db import SessionLocal
from app.models import Document, DocumentExtraction, Quote, FieldCorrection, Approval, PurchaseHistory
from app.providers import LocalStorageProvider
from app.seed import sid

FILES = [
    "synthetic-001-standard_table.pdf",
    "synthetic-002-supplier_sku_and_mpn.scan.pdf",
    "synthetic-003-comma_thousands.png",
    "synthetic-005-lead_time_range.xlsx",
    "synthetic-006-weeks.csv",
    "reliability-013-missing_quantity.xlsx",
    "reliability-006-injection.pdf",
]


def main():
    org = sid("reliability-lab")
    with SessionLocal() as db:
        for table in (Approval, PurchaseHistory):
            assert db.scalar(select(func.count()).select_from(table).where(table.organization_id == org)) == 0
        rows = []
        for name in FILES:
            doc = db.scalar(select(Document).where(Document.organization_id == org, Document.filename == name))
            assert doc and doc.stage == "Complete"
            assert hashlib.sha256(LocalStorageProvider().path(doc.storage_key).read_bytes()).hexdigest() == doc.sha256
            q = db.scalar(select(Quote).where(Quote.document_id == doc.id, Quote.organization_id == org))
            ex = db.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id))
            assert q and ex and ex.provider == "local"
            assert ex.diagnostics["model"] == "qwen2.5vl:7b" and ex.diagnostics["fallback"] is False
            assert ex.diagnostics["pipeline_version"] == "local-2.5.2"
            original = ex.diagnostics["original_ai_payload"]
            corrections = list(db.scalars(select(FieldCorrection).where(FieldCorrection.quote_id == q.id)))
            for c in corrections:
                assert c.provenance["document_id"] == doc.id and c.created_at and c.corrected_by
                key = c.field.split(".")[-1]
                if c.field.startswith("line."):
                    index = ex.diagnostics["line_ids"][c.field.split(".")[1]]
                    expected = original["line_items"][index].get(key)
                else:
                    expected = original.get(key)
                assert c.provenance["original_ai_value"] == expected
            if name == FILES[0]:
                edits = [
                    c
                    for c in corrections
                    if c.field.endswith("unit_price") and Decimal(str(c.corrected_value["value"])) == Decimal("1.35")
                ]
                assert edits and all(Decimal(str(c.provenance["original_ai_value"])) == Decimal("1.25") for c in edits)
            if name == FILES[5]:
                assert ex.payload["line_items"][0]["quantity"] is None
                assert ex.diagnostics["derived_total"] is None
            if name == FILES[6]:
                assert ex.diagnostics["needs_review"]
                assert any(f["code"] == "DOCUMENT_INSTRUCTION_TEXT_DETECTED" for f in ex.diagnostics["findings"])
                assert ex.payload["line_items"][0]["moq"] in (None, "500")
            rows.append(
                {
                    "file": name,
                    "document_id": doc.id,
                    "quote_id": q.id,
                    "sha256": doc.sha256,
                    "diagnostics": ex.diagnostics,
                    "accepted_extraction": ex.payload,
                    "corrections": [
                        {
                            "field": c.field,
                            "previous": c.original_value,
                            "corrected": c.corrected_value,
                            "provenance": c.provenance,
                            "timestamp": c.created_at.isoformat(),
                        }
                        for c in corrections
                    ],
                }
            )
        print(
            json.dumps(
                {"status": "PASS", "documents": rows, "evaluation_approvals": 0, "evaluation_purchase_history": 0},
                default=str,
            )
        )


if __name__ == "__main__":
    main()
