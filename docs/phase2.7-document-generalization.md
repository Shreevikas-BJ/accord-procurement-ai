# Phase 2.7 — local document structure generalization

Phase 2.7 tested whether a heavier local structure parser could improve unseen supplier layouts before changing Qwen. The answer is **no for the tested configurations**. The current deterministic parsers remain the defaults. Docling flattened procurement rows on seven of eight evaluated digital PDFs. PP-StructureV3 accurately structured one image but did not improve final extraction, took 107.641 seconds for that page, and reached the 10 GiB memory ceiling during a four-document batch attempt.

The canonical structure boundary is complete and the application regression suite passes. The new sealed 50-document holdout reached only **49.600% critical accuracy** and **49.000% line association**, far below the 95% pilot targets. The safety boundary remained intact: 0 unsupported accepted critical values, 100% evidence match, 0 critical-error escapes, and 100% critical-error review capture. Accord is **NOT READY** for a supervised buyer pilot.

## Frozen local configuration

| Component | Version / configuration |
|---|---|
| Qwen | `qwen2.5vl:7b`, digest `5ced39dfa4bac325dc183dd1e4febaa1c46b3ea28bce48896c8e69c1e79611cc`, Q4_K_M |
| Ollama | 0.30.11, native `/api/chat`, temperature 0, context 8,192, output budget 3,500 |
| Prompt / pipeline | `quote-v4` / `local-2.7.0` |
| Docling | 2.126.0; CPU-only PyTorch 2.10.0 image; default layout model `docling-project/docling-layout-heron` |
| PaddleOCR / PaddlePaddle | 3.7.0 / 3.3.1; PP-StructureV3 on CPU; MKL-DNN disabled after an incompatible runtime conversion error |
| Existing PDF | pdfplumber 0.11.10, pypdf 6.18.0, pypdfium2 5.13.0 |
| Existing OCR | pytesseract 0.3.13 and system Tesseract; Poppler rendering |
| Spreadsheet / image | openpyxl 3.1.5, Python CSV, Pillow 12.3.0 |

No hosted model, hosted OCR, external document telemetry, or paid API was introduced. Supplier files remained on the local machine and local Docker network. Inference concurrency remained one through the shared Redis lease.

Docling used its default `DocumentConverter` pipeline in an isolated CPU-only image. No table or page result was hand-corrected before scoring. PP-StructureV3 used `device="cpu"`, document-orientation classification and text-line orientation, with table recognition enabled. Document unwarping, seal recognition, formula recognition, chart recognition, and region detection were disabled; `enable_mkldnn=False` avoided the observed oneDNN/PIR runtime incompatibility. Both tools emitted stable JSON before Accord converted the results to canonical rows.

## Licenses reviewed

The Docling code and `docling-ibm-models` Python package report MIT licensing. Model licensing was checked separately: the tested [Docling layout Heron model](https://huggingface.co/docling-project/docling-layout-heron/tree/main) reports Apache-2.0, while the broader [Docling models repository](https://huggingface.co/docling-project/docling-models) exposes separate CDLA-Permissive-2.0 and Apache-2.0 tags. A future adoption must record the exact model and license rather than treating every optional Docling model as MIT. The [Docling repository](https://github.com/docling-project/docling) and [installation guide](https://docling-project.github.io/docling/getting_started/installation/) were also reviewed.

PaddleOCR and PaddlePaddle use Apache-2.0-compatible project licensing. The tested setup followed the local [PaddleOCR repository](https://github.com/PaddlePaddle/PaddleOCR), [quick start](https://www.paddleocr.ai/main/en/quick_start.html), and [PaddlePaddle installation guidance](https://www.paddleocr.ai/v3.5.0/en/version3.x/paddlepaddle_installation.html). PP-ChatOCR and hosted ERNIE were not used.

## Canonical structure and routing

`DocumentStructureProvider` now produces a provider-neutral `CanonicalDocument` containing pages, text blocks, tables, rows, cells, provenance, parser metadata, and source format. Cells retain raw and normalized values, semantic headers, coordinates when available, confidence, source references, and ambiguity flags. Procurement and evidence code do not receive Docling or Paddle objects.

The deterministic quality assessment records table count, usable row count, procurement headers, column consistency, SKU-shaped tokens, and numeric rows. It assigns `STRONG_STRUCTURE`, `WEAK_STRUCTURE`, or `NO_STRUCTURE`; weak or failed optional providers fall back to the current parser. Optional-parser exceptions cannot bypass the established route.

Final routing is:

- Digital PDF: current pdfplumber text, tables, and coordinate rows.
- Scanned PDF, PNG, and JPG: current Tesseract OCR geometry, with bounded Qwen vision only when parser quality remains low.
- XLSX and CSV: current openpyxl/Python CSV rows and cells, converted to the canonical representation.
- TXT: bounded plain text represented as canonical blocks.
- Docling and Paddle adapters remain available behind the stable boundary for future isolated experiments; neither dependency is installed in the API or worker image.

## Structure parser benchmark

The fixed development subset contained 16 documents. Docling was evaluated on its eight digital PDFs. PP-StructureV3 completed one planned scan/image case before resource evidence made continued batching unsafe and noncompetitive.

| Structure metric | Current parser, 16 docs | Docling, 8 PDFs | Paddle, 1 image |
|---|---:|---:|---:|
| Table detection | 87.500% | 12.500% | 100.000% |
| Expected lines recovered | 84.615% | 0.000% | 100.000% |
| Row-count accuracy | 87.500% | 0.000% | 100.000% |
| Header detection | 87.500% | 0.000% | 100.000% |
| SKU preservation | 100.000% | 100.000% | 100.000% |
| Quantity preservation | 100.000% | 100.000% | 100.000% |
| Unit-price preservation | 94.872% | 100.000% | 100.000% |
| Decimal preservation | 94.872% | 100.000% | 100.000% |
| Currency preservation | 100.000% | 100.000% | 100.000% |
| Row association | 79.487% | 0.000% | 100.000% |
| Missing-row rate | 15.385% | 100.000% | 0.000% |
| Reading order | 81.250% | 0.000% | 100.000% |
| Median latency | 0.576 s | 0.622 s | 107.641 s |
| P95 latency | 1.666 s | 26.578 s | 107.641 s |

Docling preserved visible tokens but did not preserve their procurement table relationships. It selected an unrelated table in the 20-page case. On the same eight PDFs, the current-parser-to-Qwen path reached 100% critical accuracy, 100% line association, and 100% processing success. Docling-to-unchanged-Qwen reached 2.273%, 0%, and 87.5% respectively.

Paddle reached 100% structure line recovery and association on `synthetic-003-comma_thousands.png`. The unchanged final extractor then reached 92.857% critical accuracy and 100% association, compared with 100% and 100% through current Tesseract geometry. The candidate took 107.641 seconds versus 0.662 seconds for current structure processing. Its four-document batch produced no completed output before a safety stop after approximately 3 minutes 40 seconds at the explicit 10 GiB memory limit; measured peak CPU was 522.12%, exit code 143, and Docker did not report an OOM kill.

The isolated CPU images were 1,166,495,618 bytes for Docling and 2,163,006,934 bytes for Paddle. These costs are not present in the production API or worker images.

## Development benchmark

The final 144-document run used the same Qwen and prompt as the frozen Phase 2.6 baseline. The structure boundary did not change development accuracy.

| Metric | Phase 2.6 baseline | Phase 2.7 final |
|---|---:|---:|
| Critical accuracy | 99.588% | 99.588% |
| Line association | 99.658% | 99.658% |
| Supplier | 99.306% | 99.306% |
| SKU | 99.658% | 99.658% |
| Quantity | 99.658% | 99.658% |
| Unit price | 99.658% | 99.658% |
| Currency | 99.306% | 99.306% |
| Schema / processing success | 99.306% | 99.306% |
| Review trigger | 63.194% | 63.194% |
| Median total latency | 6.419 s | 5.562 s |
| P95 total latency | 11.810 s | 10.569 s |

Repeated-line correctness remained 7/7 and tiered-pricing correctness remained 2/2. The final development safety report measured 0/112 missing-field hallucinations, 0/1,413 unsupported accepted critical values, 100% evidence match, 0/144 critical escapes, and 100% review capture for the single critical-error document. Fourteen instruction-bearing documents produced 0 accepted manipulations.

## Independent Phase 2.7 holdout

The sealed manifest SHA-256 is `593131477a2a8518f9410cf14e28b7544a87e0d658bb55fee503aebd09ce78af`. It contains 50 independently generated documents: 15 digital PDFs, 10 scanned PDFs, 5 JPGs, 5 PNGs, 5 XLSX files, 5 CSV files, and 5 text files. Every source hash was checked before inference. Ground truth was opened only after each extraction. No holdout result changed the frozen parser routing, Qwen model, prompt, settings, or evidence policy.

| Holdout metric | Result |
|---|---:|
| Schema / processing success | 100.000% |
| Critical accuracy | 49.600% |
| Line association | 49.000% |
| Supplier | 10.000% |
| SKU | 66.000% |
| Quantity | 60.000% |
| Unit price | 67.000% |
| Currency | 0.000% |
| Review trigger | 100.000% |
| Median total latency | 3.885 s |
| P95 total latency | 6.831 s |

| Format | Documents | Critical accuracy | Line association | Processing success |
|---|---:|---:|---:|---:|
| Digital PDF | 15 | 46.667% | 33.333% | 100.000% |
| Scanned PDF | 10 | 26.000% | 25.000% | 100.000% |
| JPG | 5 | 38.000% | 40.000% | 100.000% |
| PNG | 5 | 16.000% | 0.000% | 100.000% |
| XLSX | 5 | 80.000% | 100.000% | 100.000% |
| CSV | 5 | 90.000% | 100.000% | 100.000% |
| TXT | 5 | 80.000% | 100.000% | 100.000% |

The deterministic current structure layer on these 50 documents detected tables in 78%, recovered 76% of expected lines, associated 76% of rows, preserved 94% of SKUs and 100% of quantity, price, decimal, and currency tokens. It had a 24% missing-row rate, 6% duplicate-row rate, and 74% reading-order accuracy. These measurements explain part of the visual-layout gap, but final extraction also omitted identity, currency, MOQ, lead-time, and delivery fields that were present as tokens.

The dominant final error class was `MISSING_FIELD` with 610 field errors, followed by 28 UOM errors, 12 SKU errors, one supplier error, and one decimal error. Four duplicate/repeated-line holdout documents produced two duplicate-line errors. The holdout safety audit measured 0/290 unsupported accepted critical values, 100% evidence match, 0/50 critical escapes, and 50/50 critical-error review capture. This holdout contained no intentionally missing-field or prompt-injection cases, so those denominators are zero; the frozen development reliability suite supplies those safety measurements.

### Infrastructure interruption record

The first document-processing attempt was invalidated before model inference because the Accord stack was down: the inference lock could not reach Redis. Its aggregate recorded `ConnectionError` for all 50 documents, zero model time, and the image package reported `local-2.6.1` because the container working directory preceded the mounted Phase 2.7 source. No individual failure was inspected and no code, model, prompt, parser route, configuration, or label changed. The complete invalid result is retained in `phase27-holdout-infrastructure-failure`. After Redis was started, the exact context was checked as `local-2.7.0`, `quote-v4`, Redis `True`, and Ollama `Available`; the valid result in `phase27-holdout-final` then ran once without retries or service interruption.

## Application regression and runtime

The live integration suite initially exposed an all-null persistence defect: evidence hardening withheld every unsupported field from an unknown PDF, but persistence still created an empty quote. A deterministic guard now sends an extraction with no supported supplier, identifier, currency, or critical line fact to Review Required without creating a quote. This operates after extraction and evidence hardening and does not alter the sealed benchmark path. The fixed integration suite passed in full.

Verification completed on September 14, 2026:

- 149 backend tests passed; Ruff passed.
- 15/15 live Docker integration tests passed.
- PostgreSQL lifecycle passed with fresh migration `0002_local_extraction`, exact seed counts, and idempotent reseeding.
- 9/9 opt-in real-Ollama tests passed with no fixture fallback.
- All four Playwright flows passed: local five-format extraction, reliability/evidence workflow, full buyer decision workflow, and PDF/XLSX/CSV background uploads.
- Agent-browser showed a legible login page, successful sign-in, complete authenticated dashboard navigation, no framework overlay, and an empty console-error capture.
- The read-only five-format workflow verifier passed with source hashes, local model provenance, supplier/item matching, and zero evaluation purchases or approvals.
- RFQ-1003 still recommends Meridian Components at USD 118,980.00 and 94/100.

Docker 29.7.2 reported 32 logical CPUs and a 15.27 GiB memory allocation. The final idle snapshot was API 133.9 MiB, web 123.6 MiB, worker 34.33 MiB, Redis 12.71 MiB, and PostgreSQL 83.83 MiB. The RTX 5060 Laptop GPU reported 8,151 MiB total VRAM, 7,667 MiB used with Qwen resident after testing, and 4% GPU utilization. Before model loading, the Phase 2.7 baseline recorded approximately 940 MiB VRAM used. All five Compose services finished healthy.

## Decision and next work

Docling did not materially outperform the current digital PDF parser. PP-StructureV3 did not materially outperform the current Tesseract geometry path and was operationally unsuitable on this laptop. Neither becomes the default.

The current parser wins for every production format in this phase: pdfplumber/current structured parsing for digital PDF, Tesseract/current geometry for scans and images, openpyxl/Python CSV for spreadsheets, and bounded text for TXT. The canonical adapters preserve a safe place to retest newer or narrower candidate configurations later.

Accord is **NOT READY** for a supervised buyer pilot because the new holdout missed the 95% critical and line-association targets by a wide margin. The exact next recommendation is to keep the current production routing and run one bounded Phase 2.8 investigation on the sealed failure taxonomy: improve deterministic header/identity and row reconstruction for digital PDF, scan, and PNG layouts using the canonical representation, validate only on a new development corpus, and create another untouched independent holdout before reconsidering pilot readiness. Do not tune against or rerun this Phase 2.7 holdout.

## Artifacts

- [Frozen pre-change runtime](phase27-baseline-runtime.json)
- [Parser decision](../benchmark-data/results/phase27-parser-matrix/decision.json) and [structure summary](../benchmark-data/results/phase27-parser-matrix/summary.json)
- [Development report](../benchmark-data/results/phase27-development-final/report.md), [summary](../benchmark-data/results/phase27-development-final/summary.json), and [safety](../benchmark-data/results/phase27-development-final/safety.json)
- [Holdout manifest](../benchmark-data/phase27-holdout/manifest.json), [integrity file](../benchmark-data/phase27-holdout/MANIFEST.sha256), [final report](../benchmark-data/results/phase27-holdout-final/report.md), [summary](../benchmark-data/results/phase27-holdout-final/summary.json), and [safety](../benchmark-data/results/phase27-holdout-final/safety.json)
- [Holdout structure summary](../benchmark-data/results/phase27-holdout-structure/summary.json)
- [Invalid infrastructure attempt](../benchmark-data/results/phase27-holdout-infrastructure-failure/report.md)
