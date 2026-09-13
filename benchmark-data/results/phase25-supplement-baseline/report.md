# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v2` · Pipeline: `local-2.1`

Documents: 44. Schema valid: 97.727%. Critical fields: 97.183%. Entire document critical success: 93.182%.

Needs review trigger: 100.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 97.727% | 97.727% | 97.727% | None% |
| quote_number | 97.727% | 97.727% | 97.674% | 100.0% |
| rfq_number | 97.727% | 97.727% | 97.727% | None% |
| currency | 97.727% | 97.727% | 97.619% | 100.0% |
| supplier_sku | 97.959% | 97.959% | 97.959% | None% |
| quantity | 93.878% | 93.878% | 97.872% | 0.0% |
| uom | 97.959% | 97.959% | 97.917% | 100.0% |
| unit_price | 97.959% | 95.918% | 100.0% | 0.0% |
| moq | 97.959% | 97.959% | 97.917% | 100.0% |
| lead_time_days | 97.959% | 97.959% | 97.917% | 100.0% |
| delivery_date | 95.918% | 95.918% | 95.745% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.018 | 0.288 |
| ocr_seconds | 0.0 | 0.35 |
| model_seconds | 6.407 | 17.347 |
| validation_seconds | 0.001 | 0.001 |
| total_seconds | 6.435 | 17.357 |

## Failure taxonomy

- SCHEMA_ERROR: 11
- HALLUCINATED_FIELD: 2
- MISSING_FIELD: 1

Document-level failures (separate from field counts): {"SCHEMA_ERROR": 1}

Review finding counts: {"MISSING_COST": 73, "UNTRUSTED_INSTRUCTION": 2, "SOURCE_EVIDENCE_ERROR": 31, "MISSING_MOQ": 1, "MISSING_FIELD": 4, "DUPLICATE_LINE": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `reliability-013-missing_quantity` / `line_items.0.quantity`: expected `None`, extracted `1`. HALLUCINATED_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-015-missing_unit_price` / `supplier_name`: expected `Cobalt Valve Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-016-missing_quantity` / `line_items.0.quantity`: expected `None`, extracted `1`. HALLUCINATED_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-031-duplicate` / `line_items.1.delivery_date`: expected `2026-10-22`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
