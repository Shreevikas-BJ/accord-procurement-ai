# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v2` · Pipeline: `local-2.1`

Documents: 100. Schema valid: 97.0%. Critical fields: 96.075%. Entire document critical success: 88.0%.

Needs review trigger: 90.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 94.0% | 94.0% | 93.878% | 100.0% |
| quote_number | 94.0% | 94.0% | 93.878% | 100.0% |
| rfq_number | 92.0% | 92.0% | 92.0% | None% |
| currency | 94.0% | 94.0% | 93.878% | 100.0% |
| supplier_sku | 97.119% | 97.119% | 97.046% | 100.0% |
| quantity | 96.296% | 96.296% | 97.046% | 66.667% |
| uom | 97.119% | 97.119% | 96.97% | 100.0% |
| unit_price | 95.473% | 76.955% | 95.397% | 100.0% |
| moq | 96.296% | 96.296% | 96.234% | 100.0% |
| lead_time_days | 95.473% | 95.473% | 95.69% | 90.909% |
| delivery_date | 93.827% | 93.827% | 93.506% | 100.0% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.014 | 0.471 |
| ocr_seconds | 0.0 | 0.556 |
| model_seconds | 8.953 | 25.867 |
| validation_seconds | 0.002 | 0.004 |
| total_seconds | 9.053 | 26.921 |

## Failure taxonomy

- SCHEMA_ERROR: 54
- MISSING_FIELD: 29
- UNIT_PRICE_ERROR: 4
- WRONG_SUPPLIER: 3
- HALLUCINATED_FIELD: 3
- LEAD_TIME_ERROR: 2

Document-level failures (separate from field counts): {"SCHEMA_ERROR": 3}

Review finding counts: {"SUSPICIOUS_DATE": 1, "MISSING_FIELD": 38, "MISSING_COST": 148, "SOURCE_EVIDENCE_ERROR": 221, "MISSING_DELIVERY": 11, "MISSING_MOQ": 6, "DUPLICATE_LINE": 1, "UNTRUSTED_INSTRUCTION": 2, "ZERO_PRICE": 4, "PAGES_OMITTED": 2}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Meridian_RFQ1001-xlsx` / `quote_number`: expected `MER-1001-26`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Meridian_RFQ1002-xlsx` / `quote_number`: expected `MER-1002-26`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
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
- `synthetic-045-reordered_columns` / `supplier_name`: expected `Blue Canyon Optics`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-048-duplicate_lines` / `line_items.4.supplier_sku`: expected `GA-167.1`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-051-distractor_order_quantities` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page 1. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-062-european_dates_precision` / `supplier_name`: expected `Clearwater Cable Co`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-072-stock_and_offer_tables` / `rfq_number`: expected `REQ-8272`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
