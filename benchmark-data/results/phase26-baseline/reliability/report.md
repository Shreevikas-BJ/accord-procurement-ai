# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v3` · Pipeline: `local-2.5.2`

Documents: 44. Schema valid: 100.0%. Critical fields: 97.535%. Entire document critical success: 93.182%.

Needs review trigger: 86.364%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 97.727% | 97.727% | 97.727% | None% |
| quote_number | 100.0% | 100.0% | 100.0% | 100.0% |
| rfq_number | 100.0% | 100.0% | 100.0% | None% |
| currency | 100.0% | 100.0% | 100.0% | 100.0% |
| supplier_sku | 97.959% | 97.959% | 97.959% | None% |
| quantity | 97.959% | 97.959% | 97.872% | 100.0% |
| uom | 93.878% | 93.878% | 93.75% | 100.0% |
| unit_price | 97.959% | 97.959% | 97.917% | 100.0% |
| moq | 97.959% | 97.959% | 97.917% | 100.0% |
| lead_time_days | 97.959% | 97.959% | 97.917% | 100.0% |
| delivery_date | 89.796% | 89.796% | 89.362% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.017 | 0.292 |
| ocr_seconds | 0.0 | 0.322 |
| model_seconds | 6.884 | 20.057 |
| validation_seconds | 0.001 | 0.001 |
| total_seconds | 6.898 | 20.604 |

## Failure taxonomy

- MISSING_FIELD: 14

Document-level failures (separate from field counts): {}

Review finding counts: {"DOCUMENT_INSTRUCTION_TEXT_DETECTED": 12, "UNTRUSTED_INSTRUCTION": 2, "UNSUPPORTED_EXTRACTED_VALUE": 8, "TOTAL_COST_INCOMPLETE": 9, "MISSING_COST": 11, "MISSING_FIELD": 10, "MISSING_MOQ": 1, "CURRENCY_REVIEW_REQUIRED": 2, "DUPLICATE_LINE": 1, "POSSIBLE_DUPLICATE_LINE": 1, "SOURCE_LINE_COUNT_MISMATCH": 1, "SUBTOTAL_MISMATCH": 1, "GRAND_TOTAL_MISMATCH": 1, "SOURCE_VALUE_CONFLICT": 5, "DATE_REVIEW_REQUIRED": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `reliability-025-ocr` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-026-ocr` / `supplier_name`: expected `Oak Hill Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-031-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-033-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-034-duplicate` / `line_items.1.supplier_sku`: expected `VC-734`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
