# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v2` · Pipeline: `local-2`

Documents: 100. Schema valid: 98.0%. Critical fields: 96.758%. Entire document critical success: 91.0%.

Needs review trigger: 90.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 95.0% | 95.0% | 94.898% | 100.0% |
| quote_number | 96.0% | 96.0% | 96.939% | 50.0% |
| rfq_number | 94.0% | 94.0% | 94.0% | None% |
| currency | 97.0% | 97.0% | 96.939% | 100.0% |
| supplier_sku | 97.531% | 97.531% | 97.468% | 100.0% |
| quantity | 96.708% | 96.708% | 97.468% | 66.667% |
| uom | 97.531% | 97.531% | 97.403% | 100.0% |
| unit_price | 95.885% | 77.366% | 95.816% | 100.0% |
| moq | 96.296% | 96.296% | 96.234% | 100.0% |
| lead_time_days | 95.885% | 95.885% | 95.69% | 100.0% |
| delivery_date | 93.004% | 93.004% | 92.641% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.017 | 0.394 |
| ocr_seconds | 0.0 | 0.711 |
| model_seconds | 9.436 | 17.412 |
| validation_seconds | 0.002 | 0.003 |
| total_seconds | 9.452 | 18.075 |

## Failure taxonomy

- SCHEMA_ERROR: 43
- MISSING_FIELD: 28
- UNIT_PRICE_ERROR: 4
- WRONG_SUPPLIER: 3
- HALLUCINATED_FIELD: 3
- LEAD_TIME_ERROR: 2
- WRONG_RFQ: 1

Document-level failures (separate from field counts): {"SCHEMA_ERROR": 2}

Review finding counts: {"SUSPICIOUS_DATE": 1, "SOURCE_EVIDENCE_ERROR": 278, "MISSING_DELIVERY": 13, "MISSING_FIELD": 33, "MISSING_COST": 144, "MISSING_MOQ": 7, "DUPLICATE_LINE": 1, "UNTRUSTED_INSTRUCTION": 2, "ZERO_PRICE": 4, "PAGES_OMITTED": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Upload_Meridian_RFQ1003-xlsx` / `quote_number`: expected `MER-1003-26-REV2`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-003-comma_thousands` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-004-decimal_comma` / `supplier_name`: expected `Orion Valve Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-005-lead_time_range` / `line_items.0.lead_time_days`: expected `21`, extracted `14`. LEAD_TIME_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-008-missing_currency` / `line_items.2.delivery_date`: expected `2026-10-16`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-010-missing_quantity` / `line_items.0.quantity`: expected `None`, extracted `5`. HALLUCINATED_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-015-reordered_columns` / `line_items.0.delivery_date`: expected `2026-10-10`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-017-missing_delivery` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-023-missing_quote_number` / `line_items.2.delivery_date`: expected `2026-10-16`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-024-instruction_injection` / `line_items.0.unit_price`: expected `10.22`, extracted `0.01`. UNIT_PRICE_ERROR; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-034-decimal_comma` / `line_items.1.delivery_date`: expected `2026-10-13`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-035-lead_time_range` / `line_items.0.lead_time_days`: expected `21`, extracted `20`. LEAD_TIME_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-039-missing_price` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-042-discounted_total` / `line_items.1.delivery_date`: expected `2026-10-13`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-044-supplier_buyer_identity` / `rfq_number`: expected `REQ-8143`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-045-reordered_columns` / `line_items.0.delivery_date`: expected `2026-10-10`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-048-duplicate_lines` / `line_items.4.supplier_sku`: expected `GA-167.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-051-distractor_order_quantities` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-053-missing_quote_number` / `quote_number`: expected `None`, extracted `REQ-8152`. HALLUCINATED_FIELD; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-062-european_dates_precision` / `supplier_name`: expected `Clearwater Cable Co`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-071-wrapped_description` / `line_items.0.moq`: expected `10`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-072-stock_and_offer_tables` / `rfq_number`: expected `REQ-8272`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-075-same_sku_split_deliveries` / `line_items.1.delivery_date`: expected `2026-10-29`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
