# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v3` · Pipeline: `local-2.5.2`

Documents: 144. Schema valid: 97.222%. Critical fields: 90.591%. Entire document critical success: 79.167%.

Needs review trigger: 65.278%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 94.444% | 94.444% | 94.366% | 100.0% |
| quote_number | 97.222% | 97.222% | 97.872% | 66.667% |
| rfq_number | 95.833% | 95.833% | 95.833% | None% |
| currency | 97.222% | 97.222% | 97.143% | 100.0% |
| supplier_sku | 91.438% | 91.438% | 91.259% | 100.0% |
| quantity | 89.726% | 86.301% | 89.437% | 100.0% |
| uom | 89.726% | 89.726% | 89.247% | 100.0% |
| unit_price | 86.301% | 86.301% | 86.063% | 100.0% |
| moq | 89.384% | 85.959% | 89.199% | 100.0% |
| lead_time_days | 91.096% | 91.096% | 90.714% | 100.0% |
| delivery_date | 90.411% | 90.411% | 89.928% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.015 | 0.293 |
| ocr_seconds | 0.0 | 0.344 |
| model_seconds | 7.825 | 31.789 |
| validation_seconds | 0.001 | 0.003 |
| total_seconds | 7.837 | 32.223 |

## Failure taxonomy

- MISSING_FIELD: 157
- SCHEMA_ERROR: 72
- WRONG_SUPPLIER: 3

Document-level failures (separate from field counts): {"2 validation errors for QuoteExtraction\nline_items.1.stated_line_total\n  Decimal input should have no more than 4 decimal places [type=decimal_max_places, input_value=Decimal('980.11375'), input_type=Decimal]\n    For further information visit https": 1, "SCHEMA_ERROR": 1, "2 validation errors for QuoteExtraction\nstated_subtotal\n  Decimal input should have no more than 4 decimal places [type=decimal_max_places, input_value=Decimal('6339.22875'), input_type=Decimal]\n    For further information visit https": 1, "3 validation errors for QuoteExtraction\nstated_subtotal\n  Decimal input should have no more than 4 decimal places [type=decimal_max_places, input_value=Decimal('0.0519750'), input_type=Decimal]\n    For further information visit https": 1}

Review finding counts: {"SUSPICIOUS_DATE": 1, "SOURCE_VALUE_CONFLICT": 33, "DATE_REVIEW_REQUIRED": 4, "MISSING_DELIVERY": 25, "UNSUPPORTED_EXTRACTED_VALUE": 147, "SOURCE_LINE_COUNT_MISMATCH": 12, "MISSING_FIELD": 126, "MISSING_MOQ": 26, "DUPLICATE_LINE": 13, "POSSIBLE_DUPLICATE_LINE": 13, "SECOND_PASS_DISAGREEMENT": 6, "CURRENCY_REVIEW_REQUIRED": 4, "GRAND_TOTAL_MISMATCH": 6, "LINE_TOTAL_MISMATCH": 4, "UNIT_PRICE_SUSPECTED_DECIMAL_ERROR": 4, "DECIMAL_PLACEMENT_SUSPECT": 4, "SUBTOTAL_MISMATCH": 4, "DOCUMENT_INSTRUCTION_TEXT_DETECTED": 14, "UNTRUSTED_INSTRUCTION": 4, "ZERO_PRICE": 4, "PAGES_OMITTED": 2, "TOTAL_COST_INCOMPLETE": 9, "MISSING_COST": 11}

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
- `synthetic-074-twelve_page_scanned_selection` / `line_items.0.unit_price`: expected `7.4`, extracted `None`. MISSING_FIELD; page 9. Inspect original source and parsed row; verify label/column association before changing prompts.
- `reliability-025-ocr` / `line_items.0.uom`: expected `EA`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
