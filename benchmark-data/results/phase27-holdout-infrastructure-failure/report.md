# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v4` · Pipeline: `local-2.6.1`

Documents: 50. Schema valid: 0.0%. Critical fields: 0.0%. Entire document critical success: 0.0%.

Needs review trigger: 100.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 0.0% | 0.0% | 0.0% | None% |
| quote_number | 0.0% | 0.0% | 0.0% | None% |
| rfq_number | 0.0% | 0.0% | 0.0% | None% |
| currency | 0.0% | 0.0% | 0.0% | None% |
| supplier_sku | 0.0% | 0.0% | 0.0% | None% |
| quantity | 0.0% | 0.0% | 0.0% | None% |
| uom | 0.0% | 0.0% | 0.0% | None% |
| unit_price | 0.0% | 0.0% | 0.0% | None% |
| moq | 0.0% | 0.0% | 0.0% | None% |
| lead_time_days | 0.0% | 0.0% | 0.0% | None% |
| delivery_date | 0.0% | 0.0% | 0.0% | None% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.024 | 0.48 |
| ocr_seconds | 0.0 | 0.475 |
| model_seconds | 0.0 | 0 |
| validation_seconds | 0.0 | 0 |
| total_seconds | 3.147 | 3.894 |

## Failure taxonomy

- SCHEMA_ERROR: 900

Document-level failures (separate from field counts): {"ConnectionError": 50}

Review finding counts: {}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `phase27-holdout-001` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-002` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-003` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-004` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-005` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-006` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-007` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-008` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-009` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-010` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-011` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-012` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-013` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-014` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-015` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-016` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-017` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-018` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-019` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-020` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-021` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-022` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-023` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-024` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-025` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-026` / `supplier_name`: expected `Blue Mesa Components`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-027` / `supplier_name`: expected `Copper Ridge Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-028` / `supplier_name`: expected `Desert Signal Partners`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-029` / `supplier_name`: expected `Evergreen Controls`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `phase27-holdout-030` / `supplier_name`: expected `Aster Motion Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
