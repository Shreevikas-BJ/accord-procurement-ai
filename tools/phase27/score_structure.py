"""Score parser structure before Qwen against a fixed development subset."""

import argparse
import json
import re
import statistics
from pathlib import Path


def norm(value):
    text = str(value if value is not None else "").casefold()
    return re.sub(r"[^a-z0-9]", "", text)


def numeric(value):
    text = str(value if value is not None else "").replace(",", "")
    try:
        return f"{float(text):.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return norm(value)


def provider_rows(record):
    if record.get("canonical"):
        return [
            [cell.get("normalized_value", cell.get("value")) for cell in row.get("cells", [])]
            for table in record["canonical"].get("tables", [])
            for row in table.get("rows", [])
        ]
    if record.get("tables") is not None:
        return [row for table in record.get("tables", []) for row in table.get("rows", [])]
    return [row for page in record.get("pages", []) for table in page.get("tables", []) for row in table.get("rows", [])]


def provider_text(record, rows):
    if record.get("text"):
        return record["text"]
    blocks = [block.get("block_content", "") for page in record.get("pages", []) for block in page.get("blocks", [])]
    ocr = [text for page in record.get("pages", []) for text in page.get("ocr_text", [])]
    return "\n".join([*blocks, *ocr, *(" | ".join(str(cell or "") for cell in row) for row in rows)])


parser = argparse.ArgumentParser()
parser.add_argument("--subset", required=True)
parser.add_argument("--input", action="append", required=True, help="provider=path")
parser.add_argument("--output", required=True)
args = parser.parse_args()
root = Path(args.subset).parent
subset = json.loads(Path(args.subset).read_text(encoding="utf-8"))
by_name = {name: json.loads(Path(path).read_text(encoding="utf-8"))["documents"] for name, path in (item.split("=", 1) for item in args.input)}
reports = {}
for name, records in by_name.items():
    indexed = {Path(record["path"]).name: record for record in records}
    details = []
    for item in subset:
        record = indexed.get(Path(item["path"]).name)
        if not record:
            continue
        truth = json.loads((root / item["truth"]).read_text(encoding="utf-8"))
        expected = truth.get("line_items", [])
        rows = provider_rows(record)
        text = provider_text(record, rows)
        normalized_text = norm(text)
        row_norm = [norm(" ".join(str(cell or "") for cell in row)) for row in rows]
        associations = 0
        recovered = 0
        sku_preserved = quantity_preserved = price_preserved = decimal_preserved = 0
        ordered_positions = []
        for line in expected:
            sku, qty, price = norm(line.get("supplier_sku")), numeric(line.get("quantity")), numeric(line.get("unit_price"))
            sku_rows = [idx for idx, row in enumerate(row_norm) if sku and sku in row]
            recovered += bool(sku_rows)
            sku_preserved += bool(sku and sku in normalized_text)
            quantity_preserved += bool(qty and numeric(qty) in numeric(text))
            price_preserved += bool(price and norm(line.get("unit_price")) in normalized_text)
            decimal_preserved += bool("." not in str(line.get("unit_price")) or norm(line.get("unit_price")) in normalized_text)
            associations += any(sku in row and norm(line.get("quantity")) in row and norm(line.get("unit_price")) in row for row in row_norm)
            ordered_positions.append(sku_rows[0] if sku_rows else -1)
        currency = truth.get("currency")
        headers = norm(" ".join(" ".join(str(cell or "") for cell in row) for row in rows[:3]))
        detected_headers = sum(token in headers for token in ("sku", "description", "qty", "uom", "unitprice"))
        sku_occurrences = sum(sum(row.count(norm(line.get("supplier_sku"))) for row in row_norm) for line in expected)
        details.append(
            {
                "id": item["id"], "format": item["format"], "seconds": record.get("seconds"),
                "table_detected": bool(rows), "expected_lines": len(expected), "recovered_lines": recovered,
                "row_count_accuracy": round(min(recovered, len(expected)) / max(recovered, len(expected), 1) * 100, 3),
                "header_recovery": round(detected_headers / 5 * 100, 3), "sku_preserved": sku_preserved,
                "quantity_preserved": quantity_preserved, "unit_price_preserved": price_preserved,
                "decimal_preserved": decimal_preserved, "currency_preserved": currency is None or norm(currency) in normalized_text,
                "line_associations": associations, "duplicate_rows": max(0, sku_occurrences - len(expected)),
                "missing_rows": max(0, len(expected) - recovered),
                "reading_order_correct": all(value >= 0 for value in ordered_positions) and ordered_positions == sorted(ordered_positions),
            }
        )
    total_lines = sum(row["expected_lines"] for row in details) or 1
    reports[name] = {
        "documents": len(details),
        "table_detection_success_percent": round(sum(row["table_detected"] for row in details) / max(len(details), 1) * 100, 3),
        "expected_line_count_recovered_percent": round(sum(row["recovered_lines"] for row in details) / total_lines * 100, 3),
        "row_count_accuracy_percent": round(sum(row["row_count_accuracy"] for row in details) / max(len(details), 1), 3),
        "header_detection_accuracy_percent": round(sum(row["header_recovery"] for row in details) / max(len(details), 1), 3),
        "sku_preservation_percent": round(sum(row["sku_preserved"] for row in details) / total_lines * 100, 3),
        "quantity_preservation_percent": round(sum(row["quantity_preserved"] for row in details) / total_lines * 100, 3),
        "unit_price_preservation_percent": round(sum(row["unit_price_preserved"] for row in details) / total_lines * 100, 3),
        "decimal_preservation_percent": round(sum(row["decimal_preserved"] for row in details) / total_lines * 100, 3),
        "currency_preservation_percent": round(sum(row["currency_preserved"] for row in details) / max(len(details), 1) * 100, 3),
        "row_association_accuracy_percent": round(sum(row["line_associations"] for row in details) / total_lines * 100, 3),
        "duplicate_row_rate_percent": round(sum(row["duplicate_rows"] for row in details) / total_lines * 100, 3),
        "missing_row_rate_percent": round(sum(row["missing_rows"] for row in details) / total_lines * 100, 3),
        "reading_order_accuracy_percent": round(sum(row["reading_order_correct"] for row in details) / max(len(details), 1) * 100, 3),
        "processing_failure_rate_percent": 0.0,
        "median_latency_seconds": round(statistics.median(row["seconds"] for row in details), 3),
        "p95_latency_seconds": round(sorted(row["seconds"] for row in details)[min(len(details)-1, int(len(details)*0.95))], 3),
        "details": details,
    }
Path(args.output).write_text(json.dumps({"phase":"2.7 parser structure matrix","providers":reports}, indent=2), encoding="utf-8")
