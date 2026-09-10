"""Read-only proof of the five-format local workflow and immutable AI lineage."""

import hashlib
import json
from decimal import Decimal

from sqlalchemy import func, select

from app.db import SessionLocal
from app.engine import financials
from app.models import Approval, Document, DocumentExtraction, FieldCorrection, PurchaseHistory, Quote, QuoteItem
from app.providers import LocalStorageProvider
from app.seed import sid


FILES = [
    "synthetic-001-standard_table.pdf",
    "synthetic-002-supplier_sku_and_mpn.scan.pdf",
    "synthetic-003-comma_thousands.png",
    "synthetic-005-lead_time_range-v21.xlsx",
    "synthetic-006-weeks.csv",
]


def main():
    organization = sid("evaluation-lab")
    with SessionLocal() as db:

        def count(model, org):
            return db.scalar(select(func.count()).select_from(model).where(model.organization_id == org))

        assert count(PurchaseHistory, organization) == 0
        assert count(Approval, organization) == 0
        records = []
        for filename in FILES:
            document = db.scalar(
                select(Document).where(Document.organization_id == organization, Document.filename == filename)
            )
            assert document and document.stage == "Complete"
            assert (
                hashlib.sha256(LocalStorageProvider().path(document.storage_key).read_bytes()).hexdigest()
                == document.sha256
            )
            quote = db.scalar(
                select(Quote).where(Quote.document_id == document.id, Quote.organization_id == organization)
            )
            extraction = db.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == document.id))
            assert quote and quote.supplier_id and quote.rfq_id
            assert extraction.provider == "local"
            assert extraction.diagnostics["model"] == "qwen2.5vl:7b"
            assert extraction.diagnostics["fallback"] is False
            lines = list(db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote.id)))
            assert lines and all(line.item_id for line in lines)
            assert all(line.source_references["unit_price"]["evidence_type"] != "missing" for line in lines)
            _, subtotal, total = financials(lines, quote.shipping_cost, quote.tax)
            corrections = list(db.scalars(select(FieldCorrection).where(FieldCorrection.quote_id == quote.id)))
            for correction in corrections:
                assert correction.provenance["document_id"] == document.id
                assert correction.provenance["model"] == "qwen2.5vl:7b"
                assert correction.provenance["prompt_version"] == "quote-v2"
                assert correction.created_at and correction.corrected_by
                assert "original_ai_value" in correction.provenance
            if filename == FILES[0]:
                assert subtotal == Decimal("25") and total == Decimal("37")
                edits = [
                    c for c in corrections if c.field.endswith("unit_price") and c.corrected_value["value"] == "1.35"
                ]
                assert edits and all(Decimal(c.provenance["original_ai_value"]) == Decimal("1.25") for c in edits)
            records.append(
                {
                    "filename": filename,
                    "document_id": document.id,
                    "quote_id": quote.id,
                    "sha256_verified": True,
                    "provider": extraction.provider,
                    "model": extraction.diagnostics["model"],
                    "prompt_version": extraction.diagnostics["prompt_version"],
                    "pipeline_version": extraction.diagnostics["pipeline_version"],
                    "fallback": False,
                    "supplier_matched": True,
                    "items_matched": len(lines),
                    "original_missing_costs": [
                        field for field in ("shipping_cost", "tax") if extraction.payload.get(field) is None
                    ],
                    "original_supplier": extraction.payload.get("supplier_name"),
                    "current_supplier": quote.supplier_name,
                    "current_subtotal": str(subtotal),
                    "current_total": str(total) if total is not None else None,
                    "corrections": [
                        {
                            "field": c.field,
                            "previous_value": c.original_value,
                            "corrected_value": c.corrected_value,
                            "provenance": c.provenance,
                            "timestamp": c.created_at.isoformat(),
                            "actor": c.corrected_by,
                        }
                        for c in corrections
                    ],
                }
            )
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "organization": "Accord Evaluation Lab",
                    "verified_formats": len(records),
                    "evaluation_documents": count(Document, organization),
                    "evaluation_purchase_history": 0,
                    "evaluation_approvals": 0,
                    "apex_documents": count(Document, sid("org")),
                    "apex_purchase_history": count(PurchaseHistory, sid("org")),
                    "records": records,
                    "correction_note": "Scripted price edits/restorations and test retries are included; this is not natural buyer correction effort.",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
