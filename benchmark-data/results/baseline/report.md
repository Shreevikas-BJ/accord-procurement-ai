# Accord local extraction benchmark

Model: `qwen2.5vl:7b` · Prompt: `quote-v1` · Pipeline: `local-1`

Documents: 100. Schema valid: 64.0%. Critical fields: 60.495%. Entire document critical success: 56.0%.

Needs review trigger: 100.0%. All procurement decisions still require human approval. Fixture fallbacks: 0.

| Field | Normalized accuracy | Exact representation | Present values | Missing values |
|---|---:|---:|---:|---:|
| supplier_name | 61.0% | 61.0% | 62.245% | 0.0% |
| quote_number | 64.0% | 64.0% | 65.306% | 0.0% |
| rfq_number | 64.0% | 64.0% | 64.0% | None% |
| currency | 64.0% | 64.0% | 65.306% | 0.0% |
| supplier_sku | 61.317% | 61.317% | 61.181% | 66.667% |
| quantity | 58.848% | 58.848% | 60.338% | 0.0% |
| uom | 61.317% | 61.317% | 61.039% | 66.667% |
| unit_price | 58.848% | 47.737% | 58.159% | 100.0% |
| moq | 41.564% | 41.564% | 40.586% | 100.0% |
| lead_time_days | 57.613% | 57.613% | 57.328% | 63.636% |
| delivery_date | 58.436% | 58.436% | 58.009% | 66.667% |

Exact representation includes original JSON types/number formatting; normalized numbers use exact Decimal equality. Null correctness is reported separately. Failed documents stay in every denominator. Lines align by SKU, then source order; extra lines are penalized. Association requires matching SKU, quantity, UOM and price together.

## Timing (seconds)

| Stage | Median | P95 |
|---|---:|---:|
| parsing_seconds | 0.006 | 0.263 |
| ocr_seconds | 0.0 | 0.419 |
| model_seconds | 20.48 | 52.883 |
| validation_seconds | 0.0 | 0.001 |
| total_seconds | 20.493 | 53.283 |

## Failure taxonomy

- SCHEMA_ERROR: 795
- MISSING_FIELD: 65
- HALLUCINATED_FIELD: 7
- UNIT_PRICE_ERROR: 6
- LEAD_TIME_ERROR: 5
- WRONG_SUPPLIER: 3

Document-level failures (separate from field counts): {"SCHEMA_ERROR": 32, "MODEL_TIMEOUT": 3, "RemoteProtocolError": 1}

Review finding counts: {"SOURCE_EVIDENCE_ERROR": 772, "SUSPICIOUS_DATE": 1, "MISSING_DELIVERY": 10, "MISSING_FIELD": 16, "MISSING_MOQ": 52, "SUBTOTAL_MISMATCH": 3, "UNTRUSTED_INSTRUCTION": 2, "ZERO_PRICE": 4, "PAGES_OMITTED": 1}

## Failure examples

All documents are bundled demos or fictional synthetic data; full extracted responses are retained in results.jsonl for investigation. No live tenant data is included.

- `demo-Atlas_RFQ1003-pdf` / `supplier_name`: expected `Atlas Industrial Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Atlas_RFQ1004-pdf` / `supplier_name`: expected `Atlas Industrial Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Atlas_RFQ1005-pdf` / `supplier_name`: expected `Atlas Industrial Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Upload_Atlas_RFQ1003-pdf` / `supplier_name`: expected `Atlas Industrial Supply`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Vertex_RFQ1001-pdf` / `supplier_name`: expected `Vertex Industrial`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Vertex_RFQ1002-pdf` / `supplier_name`: expected `Vertex Industrial`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Vertex_RFQ1003-pdf` / `supplier_name`: expected `Vertex Industrial`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Vertex_RFQ1004-pdf` / `supplier_name`: expected `Vertex Industrial`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `demo-Vertex_RFQ1005-pdf` / `supplier_name`: expected `Vertex Industrial`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-001-standard_table` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-003-comma_thousands` / `supplier_name`: expected `Juniper Motion Systems`, extracted `J uniper Motion Systems`. WRONG_SUPPLIER; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-004-decimal_comma` / `supplier_name`: expected `Orion Valve Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-005-lead_time_range` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-006-weeks` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-008-missing_currency` / `supplier_name`: expected `Willow Packaging`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-010-missing_quantity` / `line_items.0.quantity`: expected `None`, extracted `5`. HALLUCINATED_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-011-tiered_pricing` / `supplier_name`: expected `Aspen Fluid Systems`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-012-discounted_total` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-013-inconsistent_line_total` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-014-supplier_buyer_identity` / `supplier_name`: expected `Harbor Fasteners`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-015-reordered_columns` / `supplier_name`: expected `Juniper Motion Systems`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-016-multiple_delivery_dates` / `supplier_name`: expected `Orion Valve Works`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-017-missing_delivery` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-018-duplicate_lines` / `supplier_name`: expected `Northstar Bearings`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-019-expired_quote` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-020-shipping_and_tax` / `supplier_name`: expected `Willow Packaging`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-021-distractor_order_quantities` / `line_items.0.moq`: expected `5`, extracted `None`. MISSING_FIELD; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-022-missing_supplier` / `supplier_name`: expected `None`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-023-missing_quote_number` / `supplier_name`: expected `Aspen Fluid Systems`, extracted `None`. SCHEMA_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.
- `synthetic-024-instruction_injection` / `line_items.0.unit_price`: expected `10.22`, extracted `0.01`. UNIT_PRICE_ERROR; page unknown. Inspect original source and parsed row; verify label/column association before changing prompts.

## Limits

Synthetic development corpus, not an independent real-world holdout. Existing demo variants share layouts. Improvement runs on this corpus measure regression/development progress, not generalization. Accuracy alone is insufficient for pilot readiness; inspect every critical error and test new supplier documents.
