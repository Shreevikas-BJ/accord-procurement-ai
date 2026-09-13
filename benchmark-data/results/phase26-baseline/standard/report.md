# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v3` · Pipeline: `local-2.5.2`

Documents: 100. Schema valid: 96.0%. Critical fields: 88.908%. Entire document critical success: 73.0%.

Needs review trigger: 56.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 93.0% | 93.0% | 92.857% | 100.0% |
| quote_number | 96.0% | 96.0% | 96.939% | 50.0% |
| rfq_number | 94.0% | 94.0% | 94.0% | None% |
| currency | 96.0% | 96.0% | 95.918% | 100.0% |
| supplier_sku | 90.123% | 90.123% | 89.873% | 100.0% |
| quantity | 88.066% | 83.951% | 87.764% | 100.0% |
| uom | 88.889% | 88.889% | 88.312% | 100.0% |
| unit_price | 83.951% | 83.951% | 83.682% | 100.0% |
| moq | 87.654% | 83.539% | 87.448% | 100.0% |
| lead_time_days | 89.712% | 89.712% | 89.224% | 100.0% |
| delivery_date | 90.535% | 90.535% | 90.043% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.012 | 0.294 |
| ocr_seconds | 0.0 | 0.362 |
| model_seconds | 9.332 | 22.889 |
| validation_seconds | 0.002 | 0.003 |
| total_seconds | 9.347 | 23.793 |

## Failure taxonomy

- MISSING_FIELD: 142
- SCHEMA_ERROR: 72
- WRONG_SUPPLIER: 3
- DECIMAL_ERROR: 1

Document-level failures (separate from field counts): {"2 validation errors for QuoteExtraction\nline_items.1.stated_line_total\n  Decimal input should have no more than 4 decimal places [type=decimal_max_places, input_value=Decimal('980.11375'), input_type=Decimal]\n    For further information visit https": 1, "SCHEMA_ERROR": 1, "2 validation errors for QuoteExtraction\nstated_subtotal\n  Decimal input should have no more than 4 decimal places [type=decimal_max_places, input_value=Decimal('6339.22875'), input_type=Decimal]\n    For further information visit https": 1, "3 validation errors for QuoteExtraction\nstated_subtotal\n  Decimal input should have no more than 4 decimal places [type=decimal_max_places, input_value=Decimal('0.0519750'), input_type=Decimal]\n    For further information visit https": 1}

Review finding counts: {"SUSPICIOUS_DATE": 1, "SOURCE_VALUE_CONFLICT": 27, "DATE_REVIEW_REQUIRED": 2, "MISSING_DELIVERY": 25, "UNSUPPORTED_EXTRACTED_VALUE": 139, "SOURCE_LINE_COUNT_MISMATCH": 11, "MISSING_FIELD": 115, "MISSING_MOQ": 25, "DUPLICATE_LINE": 12, "POSSIBLE_DUPLICATE_LINE": 12, "SECOND_PASS_DISAGREEMENT": 5, "CURRENCY_REVIEW_REQUIRED": 2, "GRAND_TOTAL_MISMATCH": 6, "LINE_TOTAL_MISMATCH": 5, "UNIT_PRICE_SUSPECTED_DECIMAL_ERROR": 5, "DECIMAL_PLACEMENT_SUSPECT": 5, "SUBTOTAL_MISMATCH": 4, "DOCUMENT_INSTRUCTION_TEXT_DETECTED": 2, "UNTRUSTED_INSTRUCTION": 2, "ZERO_PRICE": 4, "PAGES_OMITTED": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Scanned_Vertex_RFQ1004-pdf` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Scanned_Vertex_RFQ1004-png` / `rfq_number`: expected `RFQ-1004`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-002-supplier_sku_and_mpn` / `line_items.1.unit_price`: expected `2.95`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-003-comma_thousands` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-004-decimal_comma` / `line_items.1.unit_price`: expected `3.73`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-005-lead_time_range` / `line_items.0.lead_time_days`: expected `21`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-009-missing_price` / `line_items.0.supplier_sku`: expected `MT-128.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-010-missing_quantity` / `line_items.0.supplier_sku`: expected `PK-129.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-011-tiered_pricing` / `line_items.2.unit_price`: expected `7.77`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-016-multiple_delivery_dates` / `line_items.0.unit_price`: expected `7.1`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-017-missing_delivery` / `line_items.0.supplier_sku`: expected `SW-136.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-018-duplicate_lines` / `line_items.1.unit_price`: expected `9.19`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-023-missing_quote_number` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-024-instruction_injection` / `line_items.0.unit_price`: expected `10.22`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-028-fractional_quantity` / `supplier_name`: expected `Orion Valve Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-030-missing_sku` / `line_items.0.quantity`: expected `513`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-035-lead_time_range` / `line_items.0.lead_time_days`: expected `21`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-037-missing_moq` / `line_items.0.supplier_sku`: expected `SW-156.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-039-missing_price` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-048-duplicate_lines` / `line_items.4.supplier_sku`: expected `GA-167.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-051-distractor_order_quantities` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-053-missing_quote_number` / `supplier_name`: expected `Meadow Cable Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-058-fractional_quantity` / `supplier_name`: expected `Summit Tooling`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-060-missing_sku` / `line_items.0.quantity`: expected `1023`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-062-european_dates_precision` / `supplier_name`: expected `Clearwater Cable Co`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-063-alternate_column_labels` / `line_items.0.supplier_sku`: expected `BP/63-X.02`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-065-scan_written_dates` / `line_items.0.unit_price`: expected `6.5`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-072-stock_and_offer_tables` / `line_items.0.unit_price`: expected `7.2`, extracted `None`. MISSING_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-074-twelve_page_scanned_selection` / `line_items.0.unit_price`: expected `7.4`, extracted `74`. DECIMAL_ERROR; page 9. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
