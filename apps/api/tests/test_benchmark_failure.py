import hashlib
import json
import sys

from app.document_input import DocumentInput
from app.schemas import QuoteExtraction
from app.evaluation import benchmark


def test_post_extraction_validation_failure_remains_in_benchmark(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_bytes(b"Supplier quotation")
    expected = {"supplier_name": "Cedar", "currency": "USD", "line_items": [{"supplier_sku": "AX-100"}]}
    (tmp_path / "truth.json").write_text(json.dumps(expected))
    entry = {
        "id": "case",
        "path": "source.txt",
        "truth": "truth.json",
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "format": "txt",
        "origin": "synthetic",
        "scenarios": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps([entry]))

    class Provider:
        metadata = {"model": "qwen2.5vl:7b"}
        raw_response = json.dumps(expected)

        def extract(self, *args, **kwargs):
            return QuoteExtraction.model_validate(expected)

    monkeypatch.setattr(benchmark, "OllamaProvider", Provider)
    monkeypatch.setattr(benchmark, "connection_status", lambda: {"ai_connection": "Available"})
    monkeypatch.setattr(benchmark, "prepare_document", lambda _: DocumentInput("Supplier quotation"))

    def reject(*args):
        raise ValueError("SOURCE_VALIDATION: unsupported precision")

    monkeypatch.setattr(benchmark, "validate_extraction", reject)
    monkeypatch.setattr(sys, "argv", ["benchmark", "--corpus", str(tmp_path), "--output", str(tmp_path / "results")])
    benchmark.main()
    result = json.loads((tmp_path / "results" / "results.jsonl").read_text())
    assert result["extracted"] is None and result["success"] is False
    assert result["error_type"] == "SOURCE_VALIDATION"
    assert result["metrics"]["critical_correct"] == 0
    assert result["model_response"] == Provider.raw_response
