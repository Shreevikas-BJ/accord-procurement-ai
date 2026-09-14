# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v4` · Pipeline: `local-2.6.1`

Documents: 144. Schema valid: 99.306%. Critical fields: 99.588%. Entire document critical success: 99.306%.

Needs review trigger: 63.194%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 99.306% | 99.306% | 99.296% | 100.0% |
| quote_number | 99.306% | 99.306% | 99.291% | 100.0% |
| rfq_number | 97.917% | 97.917% | 97.917% | None% |
| currency | 99.306% | 99.306% | 100.0% | 75.0% |
| supplier_sku | 99.658% | 99.658% | 99.65% | 100.0% |
| quantity | 99.658% | 96.233% | 99.648% | 100.0% |
| uom | 99.658% | 99.658% | 99.642% | 100.0% |
| unit_price | 99.658% | 99.658% | 99.652% | 100.0% |
| moq | 99.658% | 96.233% | 99.652% | 100.0% |
| lead_time_days | 99.658% | 99.658% | 99.643% | 100.0% |
| delivery_date | 95.548% | 95.548% | 95.324% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.028 | 0.624 |
| ocr_seconds | 0.0 | 0.68 |
| model_seconds | 6.074 | 10.944 |
| validation_seconds | 0.003 | 0.012 |
| total_seconds | 6.419 | 11.81 |

## Failure taxonomy

- MISSING_FIELD: 14
- SCHEMA_ERROR: 11

Document-level failures (separate from field counts): {"SCHEMA_ERROR": 1}

Review finding counts: {"SUSPICIOUS_DATE": 1, "SOURCE_VALUE_CONFLICT": 54, "DATE_REVIEW_REQUIRED": 5, "MISSING_DELIVERY": 11, "UNSUPPORTED_EXTRACTED_VALUE": 19, "MISSING_FIELD": 40, "MISSING_MOQ": 5, "CURRENCY_REVIEW_REQUIRED": 3, "GRAND_TOTAL_MISMATCH": 4, "LINE_TOTAL_MISMATCH": 4, "UNIT_PRICE_SUSPECTED_DECIMAL_ERROR": 4, "DECIMAL_PLACEMENT_SUSPECT": 4, "SUBTOTAL_MISMATCH": 2, "DUPLICATE_LINE": 4, "POSSIBLE_DUPLICATE_LINE": 4, "DOCUMENT_INSTRUCTION_TEXT_DETECTED": 14, "UNTRUSTED_INSTRUCTION": 4, "ZERO_PRICE": 4, "SOURCE_ROWS_RECOVERED": 1, "PAGES_OMITTED": 2, "TOTAL_COST_INCOMPLETE": 6, "MISSING_COST": 8}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Scanned_Vertex_RFQ1004-pdf` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Scanned_Vertex_RFQ1004-png` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-002-injection` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-006-injection` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-030-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-031-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-032-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-033-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-034-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-035-currency_date` / `supplier_name`: expected `Oak Hill Controls`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
