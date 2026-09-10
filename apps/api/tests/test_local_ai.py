import json
from contextlib import nullcontext
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from app.document_input import DocumentInput, prepare_document
from app.extraction_validation import validate_extraction, normalize_uom
from app.local_ai import OllamaProvider, endpoint
from app.schemas import QuoteExtraction
from app.evaluation.metrics import evaluate


def quote(**changes):
    return QuoteExtraction.model_validate(
        {
            "supplier_name": "Cedar Components",
            "quote_number": "Q-124",
            "currency": "USD",
            "tax": "0",
            "shipping_cost": "5",
            "line_items": [
                {
                    "supplier_sku": "C-12",
                    "description": "Terminal",
                    "quantity": "10",
                    "unit_price": "4.25",
                    "uom": "EA",
                    "moq": "5",
                    "lead_time_days": 14,
                    "stated_line_total": "42.50",
                }
            ],
            **changes,
        }
    )


@pytest.fixture
def ollama(monkeypatch):
    import app.local_ai as module

    monkeypatch.setenv("AI_MODEL", "qwen2.5vl:7b")
    monkeypatch.setenv("AI_BASE_URL", "http://host.docker.internal:11434/v1")
    monkeypatch.setattr(module, "inference_lock", nullcontext)
    real_client = httpx.Client
    calls = []

    def install(responses):
        def handle(request):
            calls.append(json.loads(request.content))
            response = responses[min(len(calls) - 1, len(responses) - 1)]
            if isinstance(response, Exception):
                raise response
            return response

        monkeypatch.setattr(
            module.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs)
        )
        return calls

    return install


def response(value):
    return httpx.Response(200, json={"message": {"content": value}, "total_duration": 1000000})


def test_real_provider_contract_and_images(ollama):
    calls = ollama([response(quote().model_dump_json())])
    provider = OllamaProvider()
    result = provider.extract("source", document_input=DocumentInput("source", images=["base64"], image_pages=[2]))
    assert result.line_items[0].unit_price == Decimal("4.25")
    assert calls[0]["messages"][1]["images"] == ["base64"]
    assert calls[0]["format"] == "json" and calls[0]["options"]["num_ctx"] == 8192
    assert provider.metadata["fallback"] is False and provider.metadata["attempts"] == 1
    assert not any(k in calls[0] for k in ("tools", "tool_choice"))


def test_schema_repair_bounded_and_successful(ollama):
    calls = ollama([response('{"line_items": []}'), response(quote().model_dump_json())])
    assert OllamaProvider().extract("source").currency == "USD"
    assert len(calls) == 2
    assert "schema errors" in calls[1]["messages"][-1]["content"]


def test_schema_repair_stops_after_two_attempts(ollama):
    calls = ollama([response("not json")])
    with pytest.raises(ValueError, match="SCHEMA_ERROR"):
        OllamaProvider().extract("source")
    assert len(calls) == 2


@pytest.mark.parametrize(
    "status,body,code",
    [
        (404, {}, "MODEL_MISSING"),
        (500, {"error": "CUDA out of memory"}, "MODEL_OOM"),
        (500, {"error": "vision decode failed"}, "MODEL_HTTP_ERROR"),
    ],
)
def test_actionable_http_errors(ollama, status, body, code):
    calls = ollama([httpx.Response(status, json=body)])
    with pytest.raises(ValueError, match=code):
        OllamaProvider().extract("source")
    assert len(calls) == 1


def test_timeout_is_not_retried(ollama):
    calls = ollama([httpx.ReadTimeout("timeout")])
    with pytest.raises(ValueError, match="MODEL_TIMEOUT"):
        OllamaProvider().extract("source")
    assert len(calls) == 1


def test_connection_retry_bounded(ollama):
    calls = ollama([httpx.ConnectError("unreachable")])
    with pytest.raises(ValueError, match="MODEL_UNAVAILABLE"):
        OllamaProvider().extract("source")
    assert len(calls) == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://external.example",
        "http://host.docker.internal:11434/other",
        "http://user:secret@localhost:11434",
        "http://localhost:11434?redirect=evil",
    ],
)
def test_local_endpoint_never_routes_to_external_hosts(monkeypatch, url):
    monkeypatch.setenv("AI_BASE_URL", url)
    with pytest.raises(ValueError, match="LOCAL_ENDPOINT_INVALID"):
        endpoint()


def test_decimal_math_keeps_reported_and_derived_separate():
    q = quote(stated_subtotal="425", stated_total="430")
    q.line_items[0].stated_line_total = Decimal("425")
    result = validate_extraction(q, DocumentInput("Source document"))
    assert {"LINE_TOTAL_MISMATCH", "SUBTOTAL_MISMATCH", "GRAND_TOTAL_MISMATCH"} <= {
        f["code"] for f in result["findings"]
    }
    assert result["derived_subtotal"] == "42.50" and result["derived_total"] == "47.50"
    assert q.stated_total == Decimal("430") and q.line_items[0].unit_price == Decimal("4.25")
    assert result["confidence_band"] == "LOW"


def test_missing_values_stay_null_and_trigger_review():
    q = quote(supplier_name=None, currency=None, quote_number=None)
    q.line_items[0].quantity = None
    result = validate_extraction(q, DocumentInput("Unknown supplier document"))
    assert q.supplier_name is None and q.currency is None and q.line_items[0].quantity is None
    assert result["derived_total"] is None and result["needs_review"]


def test_visual_evidence_cannot_fabricate_quotations():
    q = quote(
        source_references={
            "supplier_name": {"page": 2, "source_text": "fabricated Cedar Components"},
            "currency": {"page": 99, "source_text": "USD"},
        }
    )
    result = validate_extraction(q, DocumentInput("[Page 2]", image_pages=[2], images=["image"], pages={2: ""}))
    assert q.source_references["supplier_name"].evidence_type == "visual"
    assert q.source_references["supplier_name"].source_text == ""
    assert q.source_references["currency"].evidence_type == "missing"
    assert any(f["code"] == "SOURCE_EVIDENCE_ERROR" for f in result["findings"])


def test_uom_aliases_do_not_convert_packages():
    assert normalize_uom("Each") == normalize_uom("PCS") == "EA"
    assert normalize_uom("BOX") == "BOX"
    assert normalize_uom("case of 12") != "EA"


def test_duplicate_lines_retained():
    q = quote()
    q.line_items.append(q.line_items[0].model_copy(deep=True))
    result = validate_extraction(q, DocumentInput("source"))
    assert len(q.line_items) == 2
    assert "DUPLICATE_LINE" in {f["code"] for f in result["findings"]}


@pytest.mark.parametrize(
    "field,value", [("quantity", "0"), ("quantity", "-1"), ("unit_price", "-1"), ("unit_price", "NaN")]
)
def test_invalid_financial_values_rejected(field, value):
    payload = quote().model_dump(mode="json")
    payload["line_items"][0][field] = value
    with pytest.raises(ValidationError):
        QuoteExtraction.model_validate(payload)


def test_failed_docs_remain_in_metric_denominators():
    expected = quote().model_dump(mode="json")
    result = evaluate(expected, None, "failed")
    assert result["critical_correct"] == 0
    assert result["fields"]["delivery_date"]["null_total"] == 1
    assert result["fields"]["delivery_date"]["null_correct"] == 0


def test_metrics_penalize_decimal_errors_and_extra_lines():
    expected = quote().model_dump(mode="json")
    actual = quote().model_dump(mode="json")
    actual["line_items"][0]["unit_price"] = "42.50"
    actual["line_items"].append(dict(actual["line_items"][0]))
    result = evaluate(expected, actual, "wrong")
    assert result["fields"]["unit_price"]["correct"] == 0
    assert result["fields"]["supplier_sku"]["total"] == 2
    assert any(e["error_type"] == "DECIMAL_ERROR" for e in result["errors"])


def test_long_pdf_selects_commercial_pages_without_rasterizing(tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas

    path = tmp_path / "long.pdf"
    c = canvas.Canvas(str(path))
    for page in range(1, 21):
        text = "Supplier identity and overview " * 10 if page == 1 else "General terms and materials information " * 10
        if page == 17:
            text = "Quotation SKU quantity unit price MOQ delivery subtotal total " * 5
        c.drawString(20, 700, text)
        c.showPage()
    c.save()
    monkeypatch.setenv("AI_MAX_PAGES", "3")
    document = prepare_document(path)
    assert 17 in document.metadata["selected_pages"]
    assert len(document.metadata["selected_pages"]) == 3
    assert document.metadata["image_count"] == 0
    assert len(document.metadata["omitted_pages"]) == 17
