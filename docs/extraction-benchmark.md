# Phase 2 extraction benchmark

This is a development benchmark using actual local Qwen inference. It is not a blinded evaluation or a claim of production accuracy.

**Final result:** 100 documents, 97% schema validity, 96.075% critical-field accuracy, 88% entire-document critical success and 90% review triggers. Median total latency was 9.053 seconds; p95 was 26.921 seconds. All 12 documents with critical errors failed or triggered review. Significant cost omissions and instruction contamination remain: Accord is **not yet ready for a buyer pilot** on this evidence.

## Corpus and isolation

The frozen corpus contains **100 documents**: all 25 existing demo quotation files and 75 fictional generated quotations. Its formats are 23 digital PDFs, 12 scanned PDFs, 11 PNGs, 10 JPGs, 16 XLSX workbooks, 16 CSV files and 12 text/email quotations. Variants share some layouts and supplier names; they are not 100 independent supplier templates.

Scenarios cover single/multiple items, supplier SKU versus manufacturer part number, punctuation, decimal commas and thousands separators, alternate headers, missing critical/optional fields, duplicate rows, split deliveries, tiers, discounts, BOX/KG quantities, stock/history distractors, instructions embedded in source text, inconsistent totals, multiple sheets, formulas without cached values, written/European/ambiguous dates, a 20-page digital PDF with pricing on page 17, and a 12-page scan with pricing on page 9. All 71 PDF pages were rendered and visually checked in contact sheets; image examples were also inspected. Images and scans are synthetic and mostly cleaner than typical phone photographs.

The manifest stores source SHA-256 hashes, format, origin, scenario labels and ground-truth paths. The runner verifies hashes before inference. Ground truth is opened only after extraction. No fixture lookup occurs. Benchmark results never enter PostgreSQL, supplier matching, live RFQs or purchase history. Only the five separate UI verification uploads use the Accord Evaluation Lab tenant.

Source audit corrected 36 absent values in the two Scanned Vertex evaluation labels: the source image does not state UOM, description, manufacturer part, lead-time bounds or delivery date. Original demo fixtures and documents were not changed. Eighteen of these values affect measured fields, including six critical UOM labels. All three runs are scored against the same audited labels; baseline responses were regraded without new inference. See [label-audit.json](../benchmark-data/label-audit.json).

## Reproduction

Start Docker/Redis and the installed Ollama service. Use the current worker image and a host-mounted output directory so results survive container replacement:

```powershell
docker compose run --rm --no-deps -e AI_MODEL=qwen2.5vl:7b -e AI_BASE_URL=http://host.docker.internal:11434 -e AI_TIMEOUT=120 -v C:/Projects/procurement_ai/benchmark-data:/evaluation worker python -m app.evaluation.benchmark --corpus /evaluation --output /evaluation/results/new-run
```

`--limit 10` is a smoke run, not the complete benchmark. `--resume` skips already recorded IDs and rejects mixed model/prompt/pipeline versions or changed source hashes. Use a new output directory after changing extraction code. The connection preflight stops an unavailable-service batch. If the service goes down during a run, `--resume --retry-unavailable` explicitly preserves those infrastructure attempts in a separate archive before retrying; do not use this to remove model/schema failures.

Corpus generators are `tools/build_extraction_corpus.py` (25 demos plus 60 scenarios), `tools/extend_extraction_corpus.py` (15 further cases) and `tools/audit_corpus_labels.py`. They need the API's existing reportlab, pypdf, Pillow, openpyxl and Poppler dependencies. Regeneration rewrites the manifest with newly generated document hashes, so do not regenerate during an active run. Frozen committed files are preferred for reproducing reported measurements.

To re-score preserved responses after an explicit source-label audit:

```powershell
docker compose run --rm --no-deps -v C:/Projects/procurement_ai/benchmark-data:/evaluation worker python -m app.evaluation.regrade --corpus /evaluation --output /evaluation/results/baseline
```

## Measurement definitions

All requested fields are measured: supplier, quote/RFQ numbers, currency, SKU, quantity, UOM, unit price, MOQ, lead time and delivery date. Critical accuracy includes supplier, currency and each line's SKU, quantity, UOM and price. It is a micro-average across fields, so documents with more lines contribute more observations. Document critical success requires every critical value to be correct. Schema validity measures a successfully parsed and validated extraction, not commercial correctness.

Exact matching includes JSON types and decimal representation. Normalized numeric matching uses exact Decimal equality; no price tolerance is used for extraction accuracy. Text normalization folds case and ordinary whitespace, preserving SKU punctuation. UOM aliases normalize Each/PCS to EA but never BOX to EA. A bare dollar symbol is not automatically assumed to mean USD. Missing-value correctness has its own denominator. Invalid/failed documents score zero even for expected nulls and remain in every denominator.

Line association aligns by SKU and source order and requires quantity, UOM and price on that same line to match. Extra rows are penalized. Reordered rows sharing an identical SKU can be over-penalized by source-order matching; inspect such examples directly.

Needs Review rate is the validator's alert trigger rate. Every production local quote still requires buyer review and human approval, including HIGH confidence. Benchmark confidence does not include database matching/history signals because the runner deliberately does not access tenant data. Human corrections/document is unmeasured for the corpus; the separate UI test measures correction persistence, not naturally occurring buyer effort.

Latency is wall-clock parsing, OCR, model, validation and total time. Model time includes bounded retries and lock wait; reported p95 uses nearest rank. Missing stage timings on failures are zero, so stage medians should be interpreted with the failure rate. End-to-end totals retain failures and their actual elapsed time.

## Baseline and changes

Baseline used `quote-v1` / `local-1`; the improved run uses `quote-v2` / `local-2`. Both use the same installed `qwen2.5vl:7b`, temperature 0, context 8,192 and selected-page limit three. Baseline inherited the former 45-second request timeout; improved uses 120 seconds. Therefore this comparison combines prompt, parser, evidence and timeout improvements rather than isolating one causal variable.

The full baseline had 64% schema validity, 60.495% critical accuracy, 56% document critical success and 100% review triggers. It retained 32 schema failures, three timeouts and one transport failure. During a session shutdown/restart, 39 unavailable-service attempts were archived and retried unchanged after recovery. Those attempts are separately preserved; they are not claimed as model successes. The final baseline contains exactly 100 document results including all actual model failures.

Repeated baseline schema errors came from model-generated `source_references` objects where the application expected dictionaries keyed by field. The improved prompt requests only business fields; the application derives and verifies references from source rows/pages. Spreadsheet input now retains structured column labels and quoted cells. Long scans receive CPU thumbnail OCR for page selection. Strict precision checks prevent database rounding, and schema repair cannot round an unsupported amount into compliance. Regression tests cover these defects and missing-value/evidence handling.

## Result artifacts

- [Baseline report](../benchmark-data/results/baseline/report.md), [summary](../benchmark-data/results/baseline/summary.json), [per-document responses](../benchmark-data/results/baseline/results.jsonl).
- [Improved report](../benchmark-data/results/improved/report.md), [summary](../benchmark-data/results/improved/summary.json), [per-document responses](../benchmark-data/results/improved/results.jsonl).
- [Final local-2.1 report](../benchmark-data/results/final/report.md), [summary](../benchmark-data/results/final/summary.json), [per-document responses](../benchmark-data/results/final/results.jsonl).
- [Observed local runtime](local-ai-runtime.json) records Ollama version, exact model digest, context, loaded GPU allocation and host GPU utilization.

Each run also produces per-field CSV and a complete failure JSON file. Raw model responses are safe here because the corpus is fictional/bundled demo material; do not enable this artifact policy for confidential buyer uploads. First ten baseline rows predate raw-response capture and legitimately lack that field.

## Complete baseline versus improved run

Each column includes all 100 documents. Three full real-model runs were completed; the final column is the current pipeline, not the best observed score.

| Metric | Baseline v1 | Improved v2 | Final local-2.1 |
|---|---:|---:|---:|
| Supplier | 61% | 95% | 94% |
| Quote number | 64% | 96% | 94% |
| RFQ number | 64% | 94% | 92% |
| Currency | 64% | 97% | 94% |
| SKU | 61.317% | 97.531% | 97.119% |
| Quantity | 58.848% | 96.708% | 96.296% |
| UOM | 61.317% | 97.531% | 97.119% |
| Unit price | 58.848% | 95.885% | 95.473% |
| MOQ | 41.564% | 96.296% | 96.296% |
| Lead time | 57.613% | 95.885% | 95.473% |
| Delivery date | 58.436% | 93.004% | 93.827% |
| Critical fields | 60.495% | 96.758% | 96.075% |
| Entire document critical success | 56% | 91% | 88% |
| Line association | 56.379% | 95.062% | 94.650% |
| Schema validity / processing success | 64% | 98% | 97% |
| Failed extraction | 36% | 2% | 3% |
| Review trigger | 100% | 90% | 90% |
| Median total latency | 20.493 s | 9.452 s | 9.053 s |
| P95 total latency | 53.283 s | 18.075 s | 26.921 s |
| Mean total latency | 25.615 s | 10.198 s | 12.570 s |
| Fixture fallback | 0 | 0 | 0 |

For the 25 existing demos, v2 schema validity was 100% and critical accuracy was 99.714%. For the 75 generated cases these were 97.333% and 95.499%. This gap reinforces the need for independent real-world testing.

**Critical accuracy alone hides a major completeness limitation:** v2 correctly captured shipping and tax on only 26 of 100 documents; 74 omitted them or failed. Of 70 source labels with reported subtotal/grand total, only eight were captured and 62 were omitted or failed. These fields are outside the defined critical metric. Missing costs kept evaluated totals unavailable, which is safe but imposes substantial buyer work. The five-format UI check explicitly exercises buyer cost entry instead of treating null as zero.

## Failures requiring attention

The improved run had two document-level schema failures. Field-level errors were 43 schema-dependent values, 28 missing values, four wrong unit prices, three supplier-name errors, three hallucinated values, two lead-time errors and one wrong RFQ. These counts are field errors, not independent failed documents.

| Source | Expected versus actual | Outcome |
|---|---|---|
| `synthetic-024-instruction_injection` | Four prices 10.22 / 11.53 / 12.84 / 14.15 became 0.01 | Qwen followed an embedded price instruction despite the prompt. Instruction detection flagged LOW / review. No approval or external action occurred. |
| `synthetic-010-missing_quantity` | Two absent quantities became 5 and 10, copied from MOQ | Hallucination; source/evidence checks triggered review. |
| `synthetic-048-duplicate_lines` | Fifth quoted row `GA-167.1`, quantity 819, price 19.58 was omitted | Missing duplicate row; review triggered. Duplicate retention in the prompt is not sufficient. |
| `synthetic-003-comma_thousands` and two similar images | `Juniper Motion Systems` became `J uniper Motion Systems` | OCR spacing error; MEDIUM / review. Counted incorrect, even though supplier matching can normalize spacing. |
| `demo-Upload_Meridian_RFQ1003-xlsx` | Quote number, RFQ number and USD were omitted | LOW / review; remaining lines were correct. |
| `synthetic-004-decimal_comma` | Extra `number_format` key persisted after repair | Strict schema failure; source retained. |
| `synthetic-062-european_dates_precision` | `01.09.2026`, `30.11.2026`, `15.10.2026` remained non-ISO | Schema failure after repair, despite a printed DD.MM.YYYY convention. High-precision totals were also omitted. |

All nine v2 documents with any incorrect critical field were either failed extractions or review-triggered. This is a finding on this corpus, not a guarantee that future critical mistakes will always be detected. Optional-field errors can still occur with HIGH confidence. Model instruction resistance is explicitly **not solved**; the safety boundary is validation, buyer review and absence of action authority.

Page selection did find the commercial page in both long-document cases: digital pages 1/2/17, zero images, 4.192 seconds; scanned pages 1/2/9, three images, 28.391 seconds. Both had all six critical fields correct. Omitted-page warnings remained visible.

The UI exposed an additional evidence defect in vertical XLSX blocks: JSON sheet/row wrappers prevented the evidence locator from following SKU-to-price label rows. `local-2.1` fixes that deterministic post-processing and prevents a spreadsheet row number from serving as price evidence. A fresh UI-only XLSX with workbook revision metadata `2` verifies the new extraction without modifying earlier source references. Its commercial cells and ground truth are unchanged; it is not an extra benchmark case. The prompt and model remain `quote-v2` / `qwen2.5vl:7b`. A separate final full-corpus run records this version.

## Final confirmation findings

The final 100-document run completed with exit code zero and three schema failures: the same decimal-comma extra-key case and European-date case, plus `synthetic-045-reordered_columns`, where an unsupported `sku` key persisted instead of `supplier_sku`. Final field-error counts were 54 schema-dependent values, 29 missing values, four wrong unit prices, three supplier-name errors, three hallucinated values and two lead-time errors. Full expected/actual values and available page references are in the final failure JSON and response JSONL.

The final run retained the instruction-contaminated prices. All 12 documents with critical errors triggered review or failed, and no automated approval exists. Review triggers do not prove all wrong optional fields are detected. Lead-time lower/upper-bound confusion remains a known example requiring source inspection.

Final shipping and tax correctness was only **23/100 each** (77 omissions/failures each). Reported subtotal and grand total were each captured correctly for **6/70** source-present labels, with 64 omissions/failures. These auxiliary completeness checks deliberately expose a weakness hidden by the critical-field score. All five UI documents originally lacked extracted shipping/tax. Costs need reliable extraction before a useful buyer pilot; current manual entry is a safeguard, not a completed automation claim.

The 25 demos had 100% schema validity and 99.143% critical accuracy in the final run; the 75 generated documents had 96% and 94.769%. The unchanged prompt/model produced some different business fields across the two improved runs despite temperature zero. No deterministic-output or repeatability guarantee is claimed. These are development runs under normal laptop activity; the final run also overlapped UI verification/build work and its model timing can include shared-lock waiting.

The evidence fix reduced SOURCE_EVIDENCE_ERROR findings from 278 in v2 to 221 in the final run, though inference differences mean this count alone is not an isolated causal estimate. All original results are retained; no selective retry or best-run substitution was used. [Workflow and test evidence](phase2-verification.md) records what passed independently of extraction accuracy.

## Remaining validation before a buyer pilot

No pilot is launched by this task. Synthetic results are insufficient to establish readiness. A supervised 3–5 buyer pilot should wait until failures and uncertainty presentation have been reviewed against new, safely anonymized supplier documents.

The next five document tests should cover:

1. Independent supplier layouts, buyer/seller identities and revised quotations with stale prices elsewhere in the file.
2. Real low-resolution, rotated and photographed tables with faint decimal points and merged/wrapped cells.
3. Multi-page and multi-sheet quotations with continuation lines, repeated SKUs, tier boundaries and split delivery schedules.
4. Currency ambiguity, decimal conventions, tax/discount/shipping treatment, high-precision amounts and quoted pack conversions.
5. Buyer review effort: missed critical errors, evidence usefulness, correction count/time and whether HIGH/MEDIUM/LOW signals predict actual mistakes.

Before fine-tuning or downloading another model, improve the failing parser/prompt/evidence cases and establish an independent holdout. A larger vision-language model could be compared later on separate hardware, with explicit authorization; no alternative model was downloaded or benchmarked here.
