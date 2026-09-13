# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v3` · Pipeline: `local-2.5.1`

Documents: 49. Schema valid: 97.959%. Critical fields: 82.399%. Entire document critical success: 46.939%.

Needs review trigger: 57.143%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 95.918% | 95.918% | 95.833% | 100.0% |
| quote_number | 97.959% | 97.959% | 97.917% | 100.0% |
| rfq_number | 93.878% | 93.878% | 93.878% | None% |
| currency | 97.959% | 97.959% | 97.917% | 100.0% |
| supplier_sku | 89.706% | 89.706% | 89.706% | None% |
| quantity | 90.441% | 88.235% | 90.299% | 100.0% |
| uom | 55.147% | 55.147% | 53.077% | 100.0% |
| unit_price | 83.824% | 83.824% | 83.704% | 100.0% |
| moq | 88.971% | 86.765% | 88.722% | 100.0% |
| lead_time_days | 94.118% | 94.118% | 93.75% | 100.0% |
| delivery_date | 94.853% | 94.853% | 94.531% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.007 | 0.268 |
| ocr_seconds | 0.0 | 0.381 |
| model_seconds | 8.302 | 24.832 |
| validation_seconds | 0.002 | 0.003 |
| total_seconds | 8.317 | 25.233 |

## Failure taxonomy

- MISSING_FIELD: 114
- SCHEMA_ERROR: 32
- WRONG_SUPPLIER: 1

Document-level failures (separate from field counts): {"InvalidOperation": 1}

Review finding counts: {"SUSPICIOUS_DATE": 1, "SOURCE_VALUE_CONFLICT": 67, "DATE_REVIEW_REQUIRED": 1, "MISSING_DELIVERY": 11, "UNSUPPORTED_EXTRACTED_VALUE": 117, "SOURCE_LINE_COUNT_MISMATCH": 5, "MISSING_FIELD": 106, "MISSING_MOQ": 14, "DUPLICATE_LINE": 6, "POSSIBLE_DUPLICATE_LINE": 6, "CURRENCY_REVIEW_REQUIRED": 1, "SECOND_PASS_DISAGREEMENT": 2, "GRAND_TOTAL_MISMATCH": 2, "LINE_TOTAL_MISMATCH": 1, "UNIT_PRICE_SUSPECTED_DECIMAL_ERROR": 1, "DECIMAL_PLACEMENT_SUSPECT": 1, "SUBTOTAL_MISMATCH": 1, "DOCUMENT_INSTRUCTION_TEXT_DETECTED": 1, "UNTRUSTED_INSTRUCTION": 1}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Scanned_Vertex_RFQ1004-pdf` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Scanned_Vertex_RFQ1004-png` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-001-standard_table` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 2. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-002-supplier_sku_and_mpn` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-003-comma_thousands` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-004-decimal_comma` / `supplier_name`: expected `Orion Valve Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-005-lead_time_range` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-006-weeks` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-007-missing_moq` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-008-missing_currency` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-009-missing_price` / `line_items.0.supplier_sku`: expected `MT-128.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-010-missing_quantity` / `line_items.0.supplier_sku`: expected `PK-129.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-011-tiered_pricing` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-012-discounted_total` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-013-inconsistent_line_total` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-014-supplier_buyer_identity` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-015-reordered_columns` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-016-multiple_delivery_dates` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-017-missing_delivery` / `line_items.0.supplier_sku`: expected `SW-136.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-018-duplicate_lines` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-019-expired_quote` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-020-shipping_and_tax` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-021-distractor_order_quantities` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-022-missing_supplier` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-023-missing_quote_number` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 2. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-024-instruction_injection` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
