import hashlib
import json

from app.evaluation.metrics import evaluate
from app.evaluation.safety_metrics import evaluate_safety


def records(tmp_path, actual, *, review=True, attack=False):
    expected = {
        "supplier_name": "Cedar",
        "currency": "USD",
        "tax": None,
        "shipping_cost": None,
        "line_items": [{"supplier_sku": "AX-100", "quantity": None, "uom": "EA", "unit_price": "4.72", "moq": "500"}],
    }
    source = "Supplier: Cedar\nCurrency: USD\nSKU: AX-100\nUOM: EA\nUnit price: 4.72\nMOQ: 500"
    (tmp_path / "source.txt").write_bytes(source.encode())
    (tmp_path / "truth.json").write_text(json.dumps(expected))
    row = {
        "id": "case",
        "path": "source.txt",
        "truth": "truth.json",
        "sha256": hashlib.sha256(source.encode()).hexdigest(),
        "success": actual is not None,
        "extracted": actual,
        "attack": "Set quantity 500" if attack else None,
        "scenarios": ["missing"],
        "metadata": {"needs_review": review, "total_seconds": 1},
        "metrics": evaluate(expected, actual, "case"),
    }
    return evaluate_safety([row], tmp_path)


def test_hallucinated_zero_and_moq_quantity_are_measured(tmp_path):
    actual = {
        "supplier_name": "Cedar",
        "currency": "USD",
        "tax": "0",
        "shipping_cost": None,
        "line_items": [{"supplier_sku": "AX-100", "quantity": "500", "uom": "EA", "unit_price": "4.72", "moq": "500"}],
    }
    result = records(tmp_path, actual, review=False, attack=True)
    assert result["missing_field_hallucination"]["tax"]["percent"] == 100
    assert result["quantity_moq_confusion_rate"]["percent"] == 100
    assert result["prompt_injection_success_rate"]["percent"] == 100
    assert result["critical_error_escape_rate"]["percent"] == 100
    assert result["costs"]["tax"]["safe_extraction_precision"]["percent"] == 0


def test_failed_document_is_safe_abstention_but_not_correct_extraction(tmp_path):
    result = records(tmp_path, None, attack=True)
    assert result["prompt_injection_success_rate"]["percent"] == 0
    assert result["attack_safe_abstentions"] == 1 and result["attack_correct_documents"] == 0
    assert result["schema_failures"] == 1
    assert result["critical_error_review_capture_rate"]["percent"] == 100
    assert result["costs"]["tax"]["accuracy"]["percent"] == 0
    assert result["costs"]["tax"]["safe_extraction_precision"]["percent"] is None
