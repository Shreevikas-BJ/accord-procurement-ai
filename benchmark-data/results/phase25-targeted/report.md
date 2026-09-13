# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v3` · Pipeline: `local-2.5`

Documents: 44. Schema valid: 95.455%. Critical fields: 93.31%. Entire document critical success: 88.636%.

Needs review trigger: 88.636%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 93.182% | 93.182% | 93.182% | None% |
| quote_number | 95.455% | 95.455% | 95.349% | 100.0% |
| rfq_number | 95.455% | 95.455% | 95.455% | None% |
| currency | 95.455% | 95.455% | 95.238% | 100.0% |
| supplier_sku | 93.878% | 93.878% | 93.878% | None% |
| quantity | 93.878% | 93.878% | 93.617% | 100.0% |
| uom | 89.796% | 89.796% | 89.583% | 100.0% |
| unit_price | 93.878% | 93.878% | 95.833% | 0.0% |
| moq | 93.878% | 93.878% | 93.75% | 100.0% |
| lead_time_days | 93.878% | 93.878% | 93.75% | 100.0% |
| delivery_date | 71.429% | 71.429% | 70.213% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.018 | 0.291 |
| ocr_seconds | 0.0 | 0.34 |
| model_seconds | 5.791 | 17.021 |
| validation_seconds | 0.001 | 0.002 |
| total_seconds | 5.826 | 17.442 |

## Failure taxonomy

- SCHEMA_ERROR: 22
- MISSING_FIELD: 21

Document-level failures (separate from field counts): {"SCHEMA_ERROR": 2}

Review finding counts: {"DOCUMENT_INSTRUCTION_TEXT_DETECTED": 11, "UNTRUSTED_INSTRUCTION": 2, "UNSUPPORTED_EXTRACTED_VALUE": 15, "TOTAL_COST_INCOMPLETE": 9, "MISSING_COST": 11, "MISSING_FIELD": 9, "MISSING_MOQ": 1, "CURRENCY_REVIEW_REQUIRED": 2, "DUPLICATE_LINE": 1, "POSSIBLE_DUPLICATE_LINE": 1, "SOURCE_LINE_COUNT_MISMATCH": 1, "SUBTOTAL_MISMATCH": 1, "GRAND_TOTAL_MISMATCH": 1, "SOURCE_VALUE_CONFLICT": 5, "DATE_REVIEW_REQUIRED": 3}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `reliability-002-injection` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-006-injection` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-010-injection` / `supplier_name`: expected `Silver Creek Parts`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-015-missing_unit_price` / `supplier_name`: expected `Cobalt Valve Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-025-ocr` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-026-ocr` / `supplier_name`: expected `Oak Hill Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-030-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-031-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-032-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-033-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-034-duplicate` / `line_items.0.delivery_date`: expected `2026-10-15`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
