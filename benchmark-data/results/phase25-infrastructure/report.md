# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v3` · Pipeline: `local-2.5.2`

Documents: 3. Schema valid: 0.0%. Critical fields: 0.0%. Entire document critical success: 0.0%.

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
| parsing_seconds | 0.005 | 0.006 |
| ocr_seconds | 0.0 | 0.0 |
| model_seconds | 0 | 0 |
| validation_seconds | 0 | 0 |
| total_seconds | 29.973 | 30.113 |

## Failure taxonomy

- SCHEMA_ERROR: 75

Document-level failures (separate from field counts): {"MODEL_BUSY": 3}

Review finding counts: {}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Atlas_RFQ1001-pdf` / `supplier_name`: expected `Atlas Industrial Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Atlas_RFQ1002-pdf` / `supplier_name`: expected `Atlas Industrial Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Atlas_RFQ1003-pdf` / `supplier_name`: expected `Atlas Industrial Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
