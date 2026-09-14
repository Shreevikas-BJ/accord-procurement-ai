# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v4` · Pipeline: `local-2.6.1`

Documents: 100. Schema valid: 100.0%. Critical fields: 100.0%. Entire document critical success: 100.0%.

Needs review trigger: 54.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 100.0% | 100.0% | 100.0% | 100.0% |
| quote_number | 100.0% | 100.0% | 100.0% | 100.0% |
| rfq_number | 98.0% | 98.0% | 98.0% | None% |
| currency | 100.0% | 100.0% | 100.0% | 100.0% |
| supplier_sku | 100.0% | 100.0% | 100.0% | 100.0% |
| quantity | 100.0% | 95.885% | 100.0% | 100.0% |
| uom | 100.0% | 100.0% | 100.0% | 100.0% |
| unit_price | 100.0% | 100.0% | 100.0% | 100.0% |
| moq | 100.0% | 95.885% | 100.0% | 100.0% |
| lead_time_days | 100.0% | 100.0% | 100.0% | 100.0% |
| delivery_date | 100.0% | 100.0% | 100.0% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.031 | 0.604 |
| ocr_seconds | 0.0 | 0.715 |
| model_seconds | 8.03 | 11.694 |
| validation_seconds | 0.003 | 0.013 |
| total_seconds | 8.587 | 12.431 |

## Failure taxonomy

- MISSING_FIELD: 2

Document-level failures (separate from field counts): {}

Review finding counts: {"SUSPICIOUS_DATE": 1, "SOURCE_VALUE_CONFLICT": 50, "DATE_REVIEW_REQUIRED": 3, "MISSING_DELIVERY": 11, "UNSUPPORTED_EXTRACTED_VALUE": 13, "MISSING_FIELD": 34, "MISSING_MOQ": 4, "CURRENCY_REVIEW_REQUIRED": 2, "GRAND_TOTAL_MISMATCH": 4, "LINE_TOTAL_MISMATCH": 4, "UNIT_PRICE_SUSPECTED_DECIMAL_ERROR": 4, "DECIMAL_PLACEMENT_SUSPECT": 4, "SUBTOTAL_MISMATCH": 2, "DUPLICATE_LINE": 2, "POSSIBLE_DUPLICATE_LINE": 2, "DOCUMENT_INSTRUCTION_TEXT_DETECTED": 2, "UNTRUSTED_INSTRUCTION": 2, "ZERO_PRICE": 4, "SOURCE_ROWS_RECOVERED": 1, "PAGES_OMITTED": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Scanned_Vertex_RFQ1004-pdf` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Scanned_Vertex_RFQ1004-png` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
