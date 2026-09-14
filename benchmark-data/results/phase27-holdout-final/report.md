# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v4` · Pipeline: `local-2.7.0`

Documents: 50. Schema valid: 100.0%. Critical fields: 49.6%. Entire document critical success: 0.0%.

Needs review trigger: 100.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 10.0% | 10.0% | 10.0% | None% |
| quote_number | 0.0% | 0.0% | 0.0% | None% |
| rfq_number | 0.0% | 0.0% | 0.0% | None% |
| currency | 0.0% | 0.0% | 0.0% | None% |
| supplier_sku | 66.0% | 66.0% | 66.0% | None% |
| quantity | 60.0% | 60.0% | 60.0% | None% |
| uom | 50.0% | 25.0% | 50.0% | None% |
| unit_price | 67.0% | 67.0% | 67.0% | None% |
| moq | 0.0% | 0.0% | 0.0% | None% |
| lead_time_days | 0.0% | 0.0% | 0.0% | None% |
| delivery_date | 0.0% | 0.0% | 0.0% | None% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.028 | 0.513 |
| ocr_seconds | 0.0 | 0.502 |
| model_seconds | 3.5 | 6.797 |
| validation_seconds | 0.002 | 0.004 |
| total_seconds | 3.885 | 6.831 |

## Failure taxonomy

- MISSING_FIELD: 610
- UOM_ERROR: 28
- SKU_EXTRACTION_ERROR: 12
- WRONG_SUPPLIER: 1
- DECIMAL_ERROR: 1

Document-level failures (separate from field counts): {}

Review finding counts: {"CURRENCY_REVIEW_REQUIRED": 50, "UNSUPPORTED_EXTRACTED_VALUE": 224, "TOTAL_COST_INCOMPLETE": 50, "MISSING_FIELD": 260, "MISSING_COST": 100, "MISSING_MOQ": 100, "MISSING_DELIVERY": 100, "SOURCE_LINE_COUNT_MISMATCH": 11, "DUPLICATE_LINE": 11, "POSSIBLE_DUPLICATE_LINE": 11}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `phase27-holdout-001` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-002` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-003` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-004` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-005` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-006` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-007` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-008` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-009` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-010` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-011` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-012` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-013` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-014` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-015` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-016` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-017` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-018` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-019` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-020` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-021` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-022` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-023` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-024` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-025` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-026` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-027` / `supplier_name`: expected `Copper Ridge Supply`, extracted `Copper Ridge Supply                           Denomination | GBP`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-028` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-029` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-030` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
