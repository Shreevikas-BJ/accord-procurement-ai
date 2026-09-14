# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v4` · Pipeline: `local-2.6.1`

Documents: 50. Schema valid: 100.0%. Critical fields: 51.815%. Entire document critical success: 28.0%.

Needs review trigger: 76.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 36.0% | 36.0% | 36.0% | None% |
| quote_number | 36.0% | 36.0% | 36.0% | None% |
| rfq_number | 36.0% | 36.0% | 36.0% | None% |
| currency | 38.0% | 38.0% | 36.735% | 100.0% |
| supplier_sku | 64.646% | 64.646% | 64.646% | None% |
| quantity | 49.495% | 49.495% | 48.98% | 100.0% |
| uom | 53.535% | 53.535% | 53.535% | None% |
| unit_price | 54.545% | 54.545% | 54.082% | 100.0% |
| moq | 78.788% | 78.788% | 78.571% | 100.0% |
| lead_time_days | 88.889% | 88.889% | 88.889% | None% |
| delivery_date | 7.071% | 7.071% | 7.071% | None% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.03 | 0.636 |
| ocr_seconds | 0.0 | 0.543 |
| model_seconds | 7.295 | 11.022 |
| validation_seconds | 0.004 | 0.011 |
| total_seconds | 7.827 | 11.121 |

## Failure taxonomy

- MISSING_FIELD: 401
- SKU_EXTRACTION_ERROR: 24
- DECIMAL_ERROR: 2

Document-level failures (separate from field counts): {}

Review finding counts: {"UNSUPPORTED_EXTRACTED_VALUE": 299, "CURRENCY_REVIEW_REQUIRED": 32, "TOTAL_COST_INCOMPLETE": 33, "MISSING_FIELD": 248, "MISSING_COST": 65, "SOURCE_VALUE_CONFLICT": 85, "SOURCE_LINE_COUNT_MISMATCH": 14, "DOCUMENT_INSTRUCTION_TEXT_DETECTED": 3, "UNTRUSTED_INSTRUCTION": 3, "MISSING_MOQ": 22, "MISSING_DELIVERY": 11, "DUPLICATE_LINE": 2, "POSSIBLE_DUPLICATE_LINE": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `holdout-001` / `supplier_name`: expected `North Cove Industrial Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-002` / `supplier_name`: expected `Ponderosa Process Equipment`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-003` / `supplier_name`: expected `Ironwood Automation Group`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-004` / `supplier_name`: expected `Saguaro Technical Products`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-005` / `supplier_name`: expected `Granite Harbor Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-006` / `supplier_name`: expected `Lighthouse Motion Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-007` / `supplier_name`: expected `Canyon Spring Instrumentation`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-008` / `supplier_name`: expected `Rainier Assembly Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-009` / `supplier_name`: expected `Copper Basin Materials`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-010` / `supplier_name`: expected `Red Mesa Electromechanical`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-011` / `supplier_name`: expected `North Cove Industrial Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-012` / `supplier_name`: expected `Ponderosa Process Equipment`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-013` / `supplier_name`: expected `Ironwood Automation Group`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-014` / `supplier_name`: expected `Saguaro Technical Products`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-015` / `supplier_name`: expected `Granite Harbor Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-016` / `supplier_name`: expected `Lighthouse Motion Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-017` / `supplier_name`: expected `Canyon Spring Instrumentation`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-018` / `supplier_name`: expected `Rainier Assembly Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-019` / `supplier_name`: expected `Copper Basin Materials`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-020` / `supplier_name`: expected `Red Mesa Electromechanical`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-021` / `supplier_name`: expected `North Cove Industrial Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-022` / `supplier_name`: expected `Ponderosa Process Equipment`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-023` / `supplier_name`: expected `Ironwood Automation Group`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-024` / `supplier_name`: expected `Saguaro Technical Products`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-025` / `supplier_name`: expected `Granite Harbor Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-026` / `supplier_name`: expected `Lighthouse Motion Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-027` / `supplier_name`: expected `Canyon Spring Instrumentation`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-028` / `supplier_name`: expected `Rainier Assembly Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-029` / `supplier_name`: expected `Copper Basin Materials`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `holdout-030` / `supplier_name`: expected `Red Mesa Electromechanical`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
