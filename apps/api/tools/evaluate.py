"""Compare extraction JSON against fixtures; never invokes an AI service."""

import argparse
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation

FIELDS = ["supplier_name", "quote_number", "rfq_number", "currency"]
LINE_FIELDS = ["supplier_sku", "quantity", "unit_price", "moq", "lead_time_days"]


def equal(a, b):
    if a is None or b is None:
        return a == b
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return str(a).strip().lower() == str(b).strip().lower()


def evaluate(expected, actual):
    results = {k: equal(expected.get(k), actual.get(k)) for k in FIELDS}
    actual_lines = {x.get("supplier_sku"): x for x in actual.get("line_items", [])}
    for index, line in enumerate(expected["line_items"]):
        candidate = actual_lines.get(line["supplier_sku"], {})
        for field in LINE_FIELDS:
            results[f"line_{index}.{field}"] = equal(line.get(field), candidate.get(field))
    return {
        "correct": sum(results.values()),
        "total": len(results),
        "accuracy": sum(results.values()) / len(results),
        "fields": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.expected.read_text()), json.loads(args.actual.read_text())), indent=2))
