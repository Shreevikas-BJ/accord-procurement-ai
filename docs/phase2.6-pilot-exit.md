# Phase 2.6 — structured extraction and pilot exit gate

Phase 2.6 preserves the Phase 2.5 evidence boundary while replacing flattened-document extraction with row- and cell-preserving candidates. The development set recovered strongly, but the single frozen holdout exposed severe generalization failures. **Decision: NOT READY for a limited 3–5 buyer pilot.**

## Frozen baseline

The pre-change benchmark was rerun from commit `074ed1175e5d83c86a5b7f8521fefc9131825da9` and committed before implementation. It used `qwen2.5vl:7b` digest `5ced39dfa4bac325dc183dd1e4febaa1c46b3ea28bce48896c8e69c1e79611cc`, Ollama 0.30.11, `quote-v3`, and `local-2.5.2`. The combined 144-document manifest hash was `f195e7112e5e1387bc6305a6b93e845276b14c707909ed52cf8a811fedd52696`.

| Metric | Phase 2.6 baseline | Final development |
|---|---:|---:|
| Documents | 144 | 144 |
| Schema/process success | 97.222% | 99.306% |
| Critical-field accuracy | 90.591% | 99.588% |
| Line association | 83.219% | 99.658% |
| Supplier | 94.444% | 99.306% |
| SKU | 91.438% | 99.658% |
| Quantity | 89.726% | 99.658% |
| UOM | 89.726% | 99.658% |
| Unit price | 86.301% | 99.658% |
| Currency | 97.222% | 99.306% |
| MOQ | 89.384% | 99.658% |
| Lead time | 91.096% | 99.658% |
| Repeated-line correctness | 50.0% | 100.0% (7/7) |
| Tiered-pricing correctness | not separately gated | 100.0% (2/2) |
| Review trigger | 65.278% | 63.194% |
| Median total latency | 9.163 s | 6.419 s |
| P95 total latency | 22.968 s | 11.810 s |

The fresh baseline differs slightly from the earlier Phase 2.5 report because it is a new inference run; the frozen runtime record and exact values are in [phase26-baseline-runtime.json](phase26-baseline-runtime.json).

## Architecture and evidence states

`structured_input.py` produces source-preserving candidates before semantic extraction:

- XLSX and CSV retain sheet, row, cell, raw value, inferred headers, and row identity. They never use vision.
- Digital PDFs use `pdfplumber` table candidates when available and coordinate-aware word rows as fallback.
- Scans and images retain Tesseract boxes and group words into geometric row candidates. Vision is sent only when parser quality is low; normal OCR and mapped rows remain the primary path.
- Compact structured candidates go to Qwen inside the untrusted-data envelope. Deterministic code handles known headers, row identity, evidence lookup, normalization, monetary labels, arithmetic checks, duplicates, and tiers.

Evidence now records `decision_status`, `reason`, `raw_candidate`, and `accepted_value` in addition to strength and source provenance. Strong consistent values are `ACCEPTED`; plausible source-backed ambiguity is `REVIEW_REQUIRED`; absent or unsupported values are `NOT_FOUND` or `REJECTED`. Only accepted values feed trusted calculations. Unknown shipping or tax still leaves total-cost comparison incomplete.

The review UI shows Accepted, Needs verification, and Not found states; source page/sheet/row/cell; candidate; and reason. A buyer may edit a value or explicitly confirm an exact review candidate. Confirmation is stored as a field correction with actor, time, document/extraction identity, model, prompt version, pipeline version, candidate, and immutable source evidence.

The ineffective broad second pass is disabled. `second_pass_mode=disabled_structured_evidence` is retained in diagnostics, with zero calls in both final runs. Structured deterministic checks replace its former unit-price/quantity reread.

## Development result

The final development run used real Qwen with `quote-v4` and `local-2.6.1` on all 144 documents. It had one scan schema failure and no fixture fallbacks. Parser/OCR/model/validation median times were 0.028/0.000/6.074/0.003 seconds; their p95 values were 0.624/0.680/10.944/0.012 seconds.

Safety results remained at the required boundary: 0/112 missing-field hallucinations, 0/12 targeted missing-document failures, 0/14 accepted injection manipulations, 0/1,413 unsupported accepted critical values, 100% accepted-critical evidence match, 0/144 critical-error escapes, and 1/1 critical-error review capture. Shipping and tax each retained 100% accepted-value precision. Duplicate-line error fell from 50% to 0/10.

The evaluation observed a median of 0 critical and 0 total `REVIEW_REQUIRED` candidates per document; four documents contained review candidates. This candidate-only measure does not include rejected/missing fields that also require buyer work, and every local quote still requires human approval.

Per-format development results were:

| Format | Documents | Process | Critical | Association | Review trigger |
|---|---:|---:|---:|---:|---:|
| Digital PDF | 30 | 100% | 100% | 100% | 43.333% |
| Scanned PDF | 19 | 94.737% | 96.552% | 97.059% | 100% |
| JPG | 12 | 100% | 100% | 100% | 100% |
| PNG | 19 | 100% | 100% | 100% | 100% |
| XLSX | 23 | 100% | 100% | 100% | 43.478% |
| CSV | 22 | 100% | 100% | 100% | 36.364% |
| Text/email | 19 | 100% | 100% | 100% | 52.632% |

Full artifacts are in [the development result directory](../benchmark-data/results/phase26-development-final/report.md).

## Independent holdout method

`tools/build_phase26_holdout.py` created a separate 50-document synthetic corpus with new fictional suppliers, layouts, column orders, vertical and two-column forms, multi-line descriptions, footer costs, mixed free text and tables, repeated rows, tiers, and multi-page cases. Distribution is 15 digital PDFs, 10 scanned PDFs, five images (three JPG and two PNG), five XLSX, five CSV, five text/email, and five difficult documents. Its frozen manifest SHA-256 is `2b5daf7a94b8f0d8f799d8791618b99790c6645aab10fc45122a398f95d91c64`.

The generator and labels were finalized before inference. Ground truth was opened only after each extraction for scoring. The frozen `quote-v4` / `local-2.6.1` pipeline was run once; no holdout-driven change or rerun followed. This is layout-independent synthetic evidence, not a substitute for real supplier documents.

## Holdout result

| Metric | Result | Pilot target |
|---|---:|---:|
| Documents | 50 | 50 |
| Schema/process success | 100% | >=99% |
| Document critical success | 28.0% | — |
| Critical-field accuracy | 51.815% | >=97.5% |
| Line association | 28.283% | — |
| Supplier | 36.0% | >=98% |
| SKU | 64.646% | >=97% |
| Quantity | 49.495% | >=98% |
| UOM | 53.535% | — |
| Unit price | 54.545% | >=98% |
| Currency | 38.0% | >=98% |
| MOQ | 78.788% | >=95% |
| Lead time | 88.889% | >=95% |
| Repeated-line correctness | 0% (0/1) | >=95% |
| Tier correctness | 100% (1/1) | — |
| Review trigger | 76.0% | reasonable burden |
| Median / P95 latency | 7.827 / 11.121 s | P95 preferably <30 s |

Holdout safety recorded 0/14 missing-field hallucinations, 0/5 targeted missing-document failures, 0/280 unsupported accepted critical values, 100% accepted-critical evidence match, 0/50 critical-error escapes, and 36/36 critical-error review capture. Shipping and tax accepted-value precision were each 100%. The conservative injection scorer reported 1/3 because any wrong non-null critical fact on an instruction-bearing document counts as a success, even when the wrong value is an unrelated OCR error; two documents safely abstained and none was fully correct. This fails the stated zero accepted-manipulation gate and must not be relabeled as a pass without causal analysis.

The holdout candidate-only review-burden medians were 0 critical and 0 total fields, with no `REVIEW_REQUIRED` candidates. That low number is a failure signal here: many values were rejected or missing rather than preserved as useful review candidates.

| Format | Documents | Critical | Association | Review trigger |
|---|---:|---:|---:|---:|
| Digital PDF | 15 | 40.667% | 0% | 100% |
| Scanned PDF | 10 | 31.0% | 0% | 100% |
| JPG | 3 | 16.667% | 0% | 100% |
| PNG | 2 | 20.0% | 0% | 100% |
| XLSX | 5 | 100% | 100% | 20% |
| CSV | 5 | 100% | 100% | 0% |
| Text/email | 5 | 60.0% | 50.0% | 80% |
| Difficult | 5 | 56.522% | 33.333% | 60% |

The main error taxonomy is 401 `MISSING_FIELD`, 24 `SKU_EXTRACTION_ERROR`, and two `DECIMAL_ERROR` observations. Examples include `holdout-001`, where all quote-level fields were withheld and OCR changed `NC/H01-1` to `strNaCp/H01-1`; `holdout-002`, where quantity, UOM, and unit price were withheld; and `holdout-025`, where unit price `6.10` became `61`. The gap is concentrated in unseen PDF/scan/image layouts and their evidence association; deterministic XLSX and CSV stayed at 100% critical accuracy.

Complete holdout artifacts are in [the final holdout result directory](../benchmark-data/results/phase26-holdout-final/report.md).

## Verification

- 141 fast backend tests passed; two upstream deprecation warnings remain.
- 15 live Docker integration tests passed.
- Two direct real-Ollama tests and seven corpus reliability tests passed with no fixture fallback.
- The core demo Playwright flow passed and verified Meridian as RFQ-1003's recommendation.
- The five-format local-AI Playwright flow and seven-document safety/provenance flow passed.
- TypeScript, ESLint, Ruff, and the production Docker web build passed.
- Fresh PostgreSQL migration `0002_local_extraction`, seed, idempotent reseed, schema check, and isolated database cleanup passed.
- All five Compose services were healthy; the worker reached Ollama 0.30.11 and the exact installed Qwen digest.

## Exit decision

**NOT READY for a limited 3–5 buyer pilot.** The development recovery and safety capture are promising, and latency is within target, but the only independent holdout missed every accuracy gate by a large margin. New PDF/scan/image layouts produced pervasive field loss and zero line association, repeated-line correctness failed, the UI received almost no uncertain candidates to confirm, and the conservative injection metric was nonzero. Further work must use new development material rather than tuning and rerunning this frozen holdout; the next independent release decision needs another untouched corpus and real supplier-document evaluation.
