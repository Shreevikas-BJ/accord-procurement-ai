# Local quotation extraction

Accord uses the existing local Ollama installation through its native `/api/chat` endpoint. The verified model on this laptop is **`qwen2.5vl:7b`**, Ollama **0.30.11**, with an NVIDIA RTX 5060 Laptop GPU. No additional model or fine-tuning is required. See [the benchmark](extraction-benchmark.md) for measured accuracy and limitations.

## Configuration

Inspect the installed model before configuring another machine:

```powershell
ollama list
ollama ps
nvidia-smi
```

If Ollama is not on PATH on this Windows installation, use `& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list`. Start the installed Ollama application if its service is unavailable. Do not reinstall or pull models merely to resolve a stopped service.

Set the root `.env` (not committed):

```dotenv
AI_MODE=local
AI_PROVIDER=ollama
AI_BASE_URL=http://host.docker.internal:11434
AI_MODEL=qwen2.5vl:7b
AI_TIMEOUT=120
AI_CONTEXT=8192
AI_MAX_PAGES=3
```

```powershell
docker compose up -d --build --wait --wait-timeout 90
docker compose exec -T worker python -c "import httpx; print(httpx.get('http://host.docker.internal:11434/api/version').json())"
```

Changing `.env` requires recreating API and worker: `docker compose up -d --force-recreate --wait api worker`. A plain restart does not load changed environment variables. Settings shows LOCAL AI, the exact configured model and live Ollama availability. Host-native API processes instead use `http://localhost:11434`; they do not automatically load the root `.env`.

## Input and inference

- Digital PDF: extract layout text and `pdfplumber` tables, retain coordinate-aware word rows, and choose the first page plus procurement-relevant pages. Long documents are bounded to 50 pages examined and at most four pages selected (three by default).
- Scanned PDF: OCR low-resolution thumbnails to find relevant pages in long scans, render selected pages at readable resolution, and group Tesseract boxes into rows. Vision is sent only when parser quality remains low.
- PNG/JPG: retain the image for vision and provide Tesseract OCR text. Images are bounded to 40 megapixels and resized to 1,600 pixels.
- CSV/XLSX: deterministic CSV/openpyxl parsing preserves sheets, rows, column labels and decimal text. Quoted commas remain in their cells. No spreadsheet screenshots. Formula cells without cached values remain absent.
- Text: pass bounded plain text directly. The text budget is 18,000 characters; oversized selected evidence fails with a clear review error rather than silently dropping text.

`quote-v4` isolates supplier content in a JSON envelope marked `UNTRUSTED_DOCUMENT_DATA` and supplies compact row/cell candidates. The system instruction requests procurement facts, explicit nulls and separate quantity/MOQ and unit/extended prices. The model receives no actions, retrieval, database access or purchasing tools. JSON mode plus Pydantic validation is used because this installed Ollama/llama.cpp build rejected the full Decimal-heavy JSON-schema grammar. The evidence acceptance pipeline is `local-2.6.1`; its field-specific source checks are the acceptance boundary. Prompt compliance alone is insufficient. See [Phase 2.6 results and limitations](phase2.6-pilot-exit.md).

Generation uses temperature 0, context 8192 and a 3500-token output budget. Selected-page OCR uses Tesseract PSM 6 with interword spacing preserved. CSV/XLSX candidates retain sheet, row and cell references; digital PDFs retain table/word rows; scans and images retain OCR boxes grouped by geometry. Vision is reserved for low-quality parsing. The former selective second pass is disabled because it produced no recoveries; structured deterministic evidence checks now resolve header, row, unit-price, line-total, repeated-line and tier associations.

Each attempt has a 120-second default timeout. Connection failures may retry once; malformed JSON/schema has one repair attempt. Repair receives only the schema, invalid output and validation errors. Unknown fields are discarded, a missing canonical SKU key can accept the `sku` alias, and dates are normalized only with unambiguous context. No source amounts are rounded to fit storage constraints. Timeouts, missing models, HTTP errors and unsupported financial precision fail safely. The RQ job budget is 600 seconds. A shared Redis lease allows one local inference at a time across workers and benchmark processes; another caller waits at most 30 seconds before an actionable busy error. A forcibly stopped caller can leave its lease until the 590-second expiration; confirm that all callers are idle before any operational cleanup.

## Validation, evidence and review

Decimal arithmetic independently calculates derived totals and compares reported line totals, subtotal and grand total (two-cent tolerance). Reported values remain separate. Missing tax/shipping does not become zero. Duplicate lines, missing critical values, tier mismatches, expired/conflicting dates, parser quality and suspicious document instructions produce review findings. Unit aliases normalize consistently, but BOX is never converted into EA without an explicit conversion.

Evidence is derived from labeled source rows/cells and checked against the specific field. A number in an MOQ cell cannot support quantity; a line total cannot support unit price. Critical supplier/SKU/quantity/UOM/price/currency values without support become null with review findings. The same policy covers MOQ, lead time, dates, costs and quote identifiers. A model omission can be populated from a unique explicit source fact; a conflicting non-null answer requires source-consistent focused verification or is withheld. No values come from ground truth, purchase history or arithmetic back-solving. Raw snippets and original AI values remain available separately from normalized accepted values.

Evidence records carry `ACCEPTED`, `REVIEW_REQUIRED`, `REJECTED`, or `NOT_FOUND` decisions plus reason, raw candidate, accepted value, strength, and source location. Extraction failures remain document-level failures. These describe the selected source, not proof that a field is absent from every page. Review-required candidates remain visible but do not silently drive ranking or totals until the buyer confirms or edits them. Unsupported visual-only values are rejected even if a page image exists. Currency requires an explicit code; `$` or supplier country alone is insufficient. Shipping/tax require a scalar labeled amount, including explicit zero. Unknown costs produce `TOTAL_COST_INCOMPLETE`, and calculated totals remain null. Source grand total/subtotal/line totals stay separate from calculated amounts.

HIGH/MEDIUM/LOW confidence is a deterministic review signal, not a calibrated probability. It combines completeness, evidence, arithmetic, OCR/vision quality, supplier/item matching and historical anomalies. Every local quote remains subject to buyer review and human approval. Review corrections and explicit candidate confirmations retain original AI value, previous value, corrected/confirmed value, field, document/extraction IDs, model, prompt/pipeline version, actor and timestamp. Source evidence remains immutable.

Failures preserve the uploaded file and extraction diagnostics, place the document in Needs Review and leave the worker available for other jobs. The buyer can retry after correcting the cause or enter/review the quotation manually.

## Privacy and modes

Local inference permits only localhost, loopback and `host.docker.internal` endpoints, disables environment proxies, and does not follow redirects to external services. Normal logs contain stage/model/timing/status metadata rather than supplier text or prices. Phase 2.5 retains the first model response and original parsed AI payload in private extraction diagnostics so reviewers can distinguish model output, deterministic acceptance and buyer corrections. These contain supplier content and must be treated like the uploaded document; they are not normal operational logs. Committed evaluation responses contain only bundled fictional data.

`AI_MODE=demo` retains deterministic SHA-matched fixtures. The production local pipeline and benchmark explicitly disable fixture fallback. An unavailable local model never silently turns an unknown supplier quotation into a demo answer. `AI_MODE=api` retains the optional hosted adapter, disabled in the verified local configuration. No external AI provider is used by local extraction.

## Troubleshooting

| Symptom | Action |
|---|---|
| Unavailable / connection refused | Start Ollama; verify host `/api/version` and worker connectivity. |
| Configured model missing | Compare AI_MODEL exactly with `ollama list`, including its tag. |
| Timeout / out of memory | Retry a smaller document or fewer selected pages; keep inference concurrency at one. |
| Invalid quotation JSON | One schema repair is automatic; persistent failure needs clearer input or manual review. |
| Precision unsupported | Source exceeds four decimal places for totals/quantity or six for unit prices; manually resolve the storage limitation without silently rounding. |
| Long scan misses commercial pages | Inspect selected-page metadata and source; split a document when necessary. |
| Settings still shows demo | Recreate API/worker after changing `.env`; confirm the actual container environment. |

## Verification commands

Run deterministic suites in demo mode first. The existing live tests intentionally create synthetic demo records.

```powershell
docker compose exec -T -e AI_MODE=demo -e REQUIRE_REDIS=false -e REDIS_URL=redis://127.0.0.1:1/0 api pytest -q
docker compose exec -T -e RUN_DOCKER_INTEGRATION=true api pytest integration/test_docker.py -q
docker compose exec -T api python -m tools.verify_postgres_lifecycle
```

After switching the running services to local mode:

```powershell
docker compose exec -T -e RUN_LOCAL_AI_TESTS=true api pytest integration/test_local_ai.py -q
docker compose cp benchmark-data api:/app/benchmark-data
docker compose exec -T api python -m tools.seed_evaluation_lab
cd apps/web
$env:E2E_LOCAL_AI='true'
npx.cmd playwright test e2e/local-ai.spec.ts
```

The opt-in browser test uploads five unknown synthetic documents in the separate Accord Evaluation Lab tenant, checks actual local-model provenance, opens source evidence, corrects a price, verifies recalculation and restores the original price. Its revised XLSX is in `benchmark-data/ui-documents`; it preserves the commercial cells of the original corpus file and permits a fresh extraction after the evidence fix. The test does not upload the benchmark corpus into Apex or create evaluation price history. Run `docker compose exec -T api python -m tools.verify_local_workflow` for read-only persistence/provenance checks. See [actual workflow results](phase2-verification.md) and the benchmark report.

For the separate seven-case reliability workflow, seed `python -m tools.seed_reliability_lab`, run `integration/test_local_reliability.py` with `RUN_LOCAL_AI_TESTS=true`, and run `e2e/local-reliability.spec.ts` with `E2E_LOCAL_RELIABILITY=true`. The lab login is `buyer@reliability.example` / `Demo2026!accord` (fictional local development credentials). The browser test requires `local-2.6.1`, covers missing quantity and an injected instruction in addition to five formats, and exercises immutable evidence during price correction. `python -m tools.verify_reliability_workflow` checks persisted source hashes and original AI provenance without mutating records.
