import hashlib
from decimal import Decimal

from sqlalchemy import select

from app.models import DocumentExtraction, FieldCorrection, Quote, QuoteItem
from app.pipeline import has_supported_quote_fact, process_document
from app.schemas import LineItemExtraction, QuoteExtraction
from app.seed import sid


def local_payload():
    return QuoteExtraction.model_validate(
        {
            "supplier_name": "Atlas Industrial Supply",
            "quote_number": "REAL-TEST-742",
            "rfq_number": "RFQ-1003",
            "currency": "USD",
            "shipping_cost": "5",
            "tax": "0",
            "line_items": [
                {
                    "supplier_sku": "AX-100",
                    "description": "Industrial Relay",
                    "quantity": "10",
                    "uom": "EA",
                    "unit_price": "4.25",
                    "moq": "1",
                    "lead_time_days": 14,
                }
            ],
        }
    )


def test_all_null_extraction_is_not_a_supported_quote():
    empty = QuoteExtraction(line_items=[LineItemExtraction()])
    assert not has_supported_quote_fact(empty)
    assert has_supported_quote_fact(local_payload())


def test_local_failure_preserves_source_and_metadata(buyer, db_factory, monkeypatch):
    monkeypatch.setenv("AI_MODE", "local")
    monkeypatch.setattr("app.routes_quotes.enqueue", lambda db, doc: None)

    def fail(self, *args):
        self.metadata = {"model": "qwen2.5vl:7b", "prompt_version": "test", "attempts": 1}
        raise ValueError("MODEL_TIMEOUT: retry with fewer pages")

    monkeypatch.setattr("app.local_ai.OllamaProvider.extract", fail)
    content = b"Supplier quote unknown, quantity 10, unit price 4.25, USD"
    result = buyer.post("/quotes/upload", files={"file": ("unknown.csv", content, "text/csv")})
    assert result.status_code == 202
    identifier = result.json()["id"]
    process_document(identifier, sid("org"))
    doc = buyer.get(f"/documents/{identifier}").json()
    assert doc["status"] == "Needs Review" and "MODEL_TIMEOUT" in doc["error"]
    assert buyer.get(f"/documents/{identifier}/file").content == content
    with db_factory() as db:
        assert db.scalar(select(Quote).where(Quote.document_id == identifier)) is None
        extraction = db.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == identifier))
        assert extraction.diagnostics["model"] == "qwen2.5vl:7b"
        assert extraction.diagnostics["success"] is False


def test_local_correction_lineage_and_decimal_recalculation(buyer, db_factory, monkeypatch):
    monkeypatch.setenv("AI_MODE", "local")
    monkeypatch.setattr("app.routes_quotes.enqueue", lambda db, doc: None)

    def extract(self, *args):
        self.metadata = {
            "model": "qwen2.5vl:7b",
            "prompt_version": "test",
            "pipeline_version": "test",
            "fallback": False,
        }
        return local_payload()

    monkeypatch.setattr("app.local_ai.OllamaProvider.extract", extract)
    source = b"Supplier,Atlas Industrial Supply\nQuote number,REAL-TEST-742\nRFQ,RFQ-1003\nCurrency,USD\nShipping,5\nTax,0\nSKU,AX-100\nQty,10\nUOM,EA\nUnit price,4.25\nMOQ,1\nLead time,14 days"
    result = buyer.post(
        "/quotes/upload", files={"file": ("new.csv", source, "text/csv")}, data={"rfq_id": sid("rfq-3")}
    )
    identifier = result.json()["id"]
    process_document(identifier, sid("org"))
    doc = buyer.get(f"/documents/{identifier}").json()
    detail = buyer.get(f"/quotes/{doc['quote_id']}").json()
    assert detail["extraction_provider"] == "local"
    assert Decimal(detail["total"]) == Decimal("47.50")
    payload = local_payload().model_dump(mode="json")
    payload.update(version=detail["version"], rfq_id=detail["rfq_id"], supplier_id=detail["supplier_id"])
    payload["line_items"][0].update(
        id=detail["line_items"][0]["id"], item_id=detail["line_items"][0]["item_id"], unit_price="4.50"
    )
    saved = buyer.put(f"/quotes/{detail['id']}/review", json=payload)
    assert saved.status_code == 200, saved.text
    assert Decimal(saved.json()["total"]) == Decimal("50.00")
    with db_factory() as db:
        correction = db.scalar(
            select(FieldCorrection).where(
                FieldCorrection.quote_id == detail["id"], FieldCorrection.field.endswith("unit_price")
            )
        )
        assert Decimal(correction.provenance["original_ai_value"]) == Decimal("4.25")
        assert correction.provenance["model"] == "qwen2.5vl:7b"
        assert correction.provenance["document_id"] == identifier
        assert correction.created_at and correction.corrected_by
        assert hashlib.sha256(source).hexdigest() == doc["sha256"]


def test_buyer_can_confirm_review_candidate_with_provenance(buyer, db_factory):
    with db_factory() as db:
        quote = db.scalar(select(Quote))
        quote_id = quote.id
        line = db.scalar(select(QuoteItem).where(QuoteItem.quote_id == quote_id))
        extraction = db.scalar(
            select(DocumentExtraction).where(DocumentExtraction.document_id == quote.document_id)
        )
        line.unit_price = None
        references = dict(line.source_references)
        references["unit_price"] = {
            **references["unit_price"],
            "decision_status": "REVIEW_REQUIRED",
            "reason": "OCR decimal spacing needs buyer verification.",
            "raw_candidate": "4.48",
            "accepted_value": None,
            "evidence_strength": "weak",
            "source_status": "AMBIGUOUS",
        }
        line.source_references = references
        diagnostics = dict(extraction.diagnostics or {})
        diagnostics.update(model="qwen2.5vl:7b", prompt_version="quote-v4", pipeline_version="local-2.6")
        extraction.diagnostics = diagnostics
        line_id = line.id
        db.commit()

    detail = buyer.get(f"/quotes/{quote_id}").json()
    target_index = next(index for index, item in enumerate(detail["line_items"]) if item["id"] == line_id)
    payload = {
        key: detail.get(key)
        for key in QuoteExtraction.model_fields
        if key != "line_items"
    }
    payload.update(
        version=detail["version"],
        supplier_id=detail["supplier_id"],
        rfq_id=detail["rfq_id"],
        confirm_review=False,
        confirmed_fields=[f"line_items.{target_index}.unit_price"],
    )
    payload["line_items"] = [
        {
            key: item.get(key)
            for key in LineItemExtraction.model_fields
        }
        | {"id": item["id"], "item_id": item["item_id"]}
        for item in detail["line_items"]
    ]
    payload["line_items"][target_index]["unit_price"] = "4.48"
    saved = buyer.put(f"/quotes/{quote_id}/review", json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["line_items"][target_index]["unit_price"] == "4.48"
    confirmation = saved.json()["extraction_diagnostics"]["field_confirmations"][
        f"line_items.{target_index}.unit_price"
    ]
    assert confirmation["candidate"] == "4.48" and confirmation["confirmed_by"]
    with db_factory() as db:
        correction = db.scalar(
            select(FieldCorrection).where(
                FieldCorrection.quote_id == quote_id,
                FieldCorrection.field == f"line.{line_id}.unit_price",
            )
        )
        assert correction.provenance["confirmation"] is True
        assert correction.provenance["candidate"] == "4.48"
