# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v4` · Pipeline: `local-2.6.1`

Documents: 44. Schema valid: 97.727%. Critical fields: 97.887%. Entire document critical success: 97.727%.

Needs review trigger: 84.091%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 97.727% | 97.727% | 97.727% | None% |
| quote_number | 97.727% | 97.727% | 97.674% | 100.0% |
| rfq_number | 97.727% | 97.727% | 97.727% | None% |
| currency | 97.727% | 97.727% | 100.0% | 50.0% |
| supplier_sku | 97.959% | 97.959% | 97.959% | None% |
| quantity | 97.959% | 97.959% | 97.872% | 100.0% |
| uom | 97.959% | 97.959% | 97.917% | 100.0% |
| unit_price | 97.959% | 97.959% | 97.917% | 100.0% |
| moq | 97.959% | 97.959% | 97.917% | 100.0% |
| lead_time_days | 97.959% | 97.959% | 97.917% | 100.0% |
| delivery_date | 73.469% | 73.469% | 72.34% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.026 | 0.626 |
| ocr_seconds | 0.0 | 0.662 |
| model_seconds | 4.142 | 6.266 |
| validation_seconds | 0.002 | 0.005 |
| total_seconds | 4.581 | 7.112 |

## Failure taxonomy

- MISSING_FIELD: 12
- SCHEMA_ERROR: 11

Document-level failures (separate from field counts): {"SCHEMA_ERROR": 1}

Review finding counts: {"DOCUMENT_INSTRUCTION_TEXT_DETECTED": 12, "UNTRUSTED_INSTRUCTION": 2, "UNSUPPORTED_EXTRACTED_VALUE": 6, "MISSING_FIELD": 6, "MISSING_MOQ": 1, "CURRENCY_REVIEW_REQUIRED": 1, "TOTAL_COST_INCOMPLETE": 6, "MISSING_COST": 8, "DUPLICATE_LINE": 2, "POSSIBLE_DUPLICATE_LINE": 2, "SOURCE_VALUE_CONFLICT": 4, "DATE_REVIEW_REQUIRED": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

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
