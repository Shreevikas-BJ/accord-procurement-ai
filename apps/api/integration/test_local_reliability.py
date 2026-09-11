"""Opt-in actual Ollama safety checks; source labels are read after inference."""

import json
import os
from pathlib import Path

import pytest

from app.document_input import prepare_document
from app.providers import extract_quote
from app.evaluation.safety_metrics import observations, same

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LOCAL_AI_TESTS") != "true", reason="Requires installed local Qwen and Redis"
)


@pytest.mark.parametrize("case_number", [1, 4, 5, 9, 13, 16, 19])
def test_actual_qwen_safety_boundary(case_number, monkeypatch):
    monkeypatch.setenv("AI_MODE", "local")
    root = Path(os.getenv("RELIABILITY_CORPUS", "/app/benchmark-data/reliability"))
    manifest = json.loads((root / "manifest.json").read_text())
    entry = next(e for e in manifest if e["id"].startswith(f"reliability-{case_number:03d}-"))
    document = prepare_document(root / entry["path"])
    metadata = {}
    result, provider = extract_quote(document.text, entry["sha256"], document, metadata, allow_fallback=False)
    expected = json.loads((root / entry["truth"]).read_text())
    actual = result.model_dump(mode="json")
    assert provider == "local" and metadata["fallback"] is False
    assert metadata["model"] == "qwen2.5vl:7b"
    for path, key, wanted, emitted in observations(expected, actual):
        if emitted is not None:
            assert same(key, wanted, emitted), (path, wanted, emitted)
    if "injection" in entry["scenarios"]:
        assert metadata["needs_review"]
    if case_number in (13, 16):
        assert result.line_items[0].quantity is None
    if case_number == 19:
        assert result.tax is None
