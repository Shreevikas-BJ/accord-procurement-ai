"""Explicit real-model smoke checks. Never run in the normal fast suite."""

import os
import pytest
from app.local_ai import connection_status, OllamaProvider

pytestmark = pytest.mark.skipif(os.getenv("RUN_LOCAL_AI_TESTS") != "true", reason="Requires installed local Qwen model")


def test_ollama_exact_model_available():
    assert os.getenv("AI_MODEL") == "qwen2.5vl:7b"
    assert connection_status()["ai_connection"] == "Available"


def test_unknown_text_real_inference():
    provider = OllamaProvider()
    quote = provider.extract(
        "Supplier: Cedar Components Ltd\nQuote number: Q-NEW-724\nCurrency: USD\nSKU: CT-74\nDescription: Copper terminal\nQuantity: 240\nUOM: EA\nUnit price: 3.25\nMOQ: 100\nLead time: 14 days\nShipping: 18\nTax: 0"
    )
    assert quote.supplier_name == "Cedar Components Ltd"
    assert quote.line_items[0].quantity == 240
    assert str(quote.line_items[0].unit_price) == "3.25"
    assert provider.metadata["fallback"] is False
