"""Opt-in real-Qwen checks for the Phase 2.8 email intake boundary.

These tests exercise only local Ollama inference. They are excluded from the
fast suite and never send email or create procurement decisions.
"""

import os
from decimal import Decimal

import pytest

from app.config import DEMO_PATH
from app.document_input import DocumentInput, prepare_document
from app.email_parser import parse_eml
from app.local_ai import OllamaProvider, connection_status


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LOCAL_AI_TESTS") != "true",
    reason="Requires installed local Qwen model",
)


def extract(text: str, document: DocumentInput | None = None):
    provider = OllamaProvider()
    result = provider.extract(text, document_input=document)
    assert provider.metadata["model"] == "qwen2.5vl:7b"
    assert provider.metadata["fallback"] is False
    return result


def assert_first_line(result, *, sku: str, quantity: str, price: str):
    line = result.line_items[0]
    assert line.supplier_sku == sku
    assert line.quantity == Decimal(quantity)
    assert line.unit_price == Decimal(price)


@pytest.mark.xfail(
    reason="qwen2.5vl:7b omitted the alphanumeric RFQ identifier in this unseen prose layout",
    strict=True,
)
def test_email_only_quote_real_qwen():
    assert connection_status()["ai_connection"] == "Available"
    result = extract(
        "Supplier: Sonoran Motion Controls\nRFQ: RFQ-QWEN-EMAIL\nQuote: SMC-910\n"
        "Currency: USD\nFor part SM-44, quantity 320 EA, our unit price is $18.75.\n"
        "Lead time: 14 days. Payment terms: Net 30."
    )
    assert result.rfq_number == "RFQ-QWEN-EMAIL"
    assert_first_line(result, sku="SM-44", quantity="320", price="18.75")


@pytest.mark.parametrize(
    ("filename", "sku", "quantity", "price"),
    [
        ("Atlas_RFQ1003.pdf", "AX-100", "5000", "5.12"),
        ("Meridian_RFQ1003.xlsx", "MRC-AX-100", "5000", "4.48"),
    ],
)
def test_email_attachment_real_qwen(filename, sku, quantity, price):
    prepared = prepare_document(DEMO_PATH / "quotes" / filename)
    result = extract(prepared.text, prepared)
    assert_first_line(result, sku=sku, quantity=quantity, price=price)


def test_revised_email_real_qwen_uses_current_body():
    parsed = parse_eml((DEMO_PATH / "emails" / "Atlas_RFQ1003_Revised.eml").read_bytes())
    current = (
        parsed.normalized_body
        + "\nRFQ: RFQ-1003\nQuote: ATL-EMAIL-28\n"
        + "Revised line: SKU AX-100, quantity 5000 EA, unit price USD 4.48."
    )
    result = extract(current)
    assert result.quote_number == "ATL-EMAIL-28"
    assert_first_line(result, sku="AX-100", quantity="5000", price="4.48")


@pytest.mark.xfail(
    reason="qwen2.5vl:7b extracted quantity and price but omitted the SKU in this negotiation sentence",
    strict=True,
)
def test_negotiation_reply_real_qwen():
    result = extract(
        "From: Desert Valve Works\nRe: RFQ-QWEN-NEG\nQuote DV-2026-41\n"
        "We can improve our offer for valve DV-88 to USD 26.40 each at quantity 750 EA.\n"
        "MOQ remains 250. Lead time is 21 days. Terms are Net 45."
    )
    assert result.rfq_number == "RFQ-QWEN-NEG"
    assert_first_line(result, sku="DV-88", quantity="750", price="26.40")

