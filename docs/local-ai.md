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

- Digital PDF: extract layout text with pypdf; choose the first page and procurement-relevant pages. Long documents are bounded to 50 pages examined and at most four pages selected (three by default).
- Scanned PDF: OCR low-resolution thumbnails to find relevant pages in long scans, then render selected pages at readable resolution. Selected sparse-text pages receive OCR and vision together.
- PNG/JPG: retain the image for vision and provide Tesseract OCR text. Images are bounded to 40 megapixels and resized to 1,600 pixels.
- CSV/XLSX: deterministic CSV/openpyxl parsing preserves sheets, rows, column labels and decimal text. Quoted commas remain in their cells. No spreadsheet screenshots. Formula cells without cached values remain absent.
- Text: pass bounded plain text directly. The text budget is 18,000 characters; oversized selected evidence fails with a clear review error rather than silently dropping text.

`quote-v2` requests business fields only and instructs the model to use null for missing information and treat document instructions as untrusted data. The benchmark found violations of both instructions; null handling and prompt-injection resistance are not guaranteed by the model. The model receives no actions, retrieval, database access or purchasing tools. JSON mode plus Pydantic validation is used because this installed Ollama/llama.cpp build rejected the full Decimal-heavy JSON-schema grammar. Validation, source review and human approval remain authoritative safeguards. The current evidence pipeline is `local-2.1`.

Each attempt has a 120-second default timeout. Connection failures may retry once; malformed JSON/schema has one repair attempt. Timeouts, missing models, HTTP errors and unsupported financial precision fail safely. Precision failures never ask the model to round source amounts. The RQ job budget is 600 seconds. A shared Redis lease allows one local inference at a time across workers and benchmark processes; another caller waits at most 30 seconds before an actionable busy error.

## Validation, evidence and review

Decimal arithmetic independently calculates derived totals and compares reported line totals, subtotal and grand total (two-cent tolerance). Reported values remain separate. Missing tax/shipping does not become zero. Duplicate lines, missing critical values, tier mismatches, expired/conflicting dates, parser quality and suspicious document instructions produce review findings. Unit aliases normalize consistently, but BOX is never converted into EA without an explicit conversion.

Evidence is derived from actual source rows/blocks, checked against the extracted value, and saved with document/page information. OCR quotes must occur in OCR text. Visual-only evidence carries a page reference and no invented quotation. Missing evidence is explicit. Multi-page visual evidence is not assigned an arbitrary page.

HIGH/MEDIUM/LOW confidence is a deterministic review signal, not a calibrated probability. It combines completeness, evidence, arithmetic, OCR/vision quality, supplier/item matching and historical anomalies. Every local quote remains subject to buyer review and human approval. Review corrections retain original AI value, previous value, corrected value, field, document/extraction IDs, model, prompt/pipeline version, actor and timestamp. Source evidence remains immutable during corrections.

Failures preserve the uploaded file and extraction diagnostics, place the document in Needs Review and leave the worker available for other jobs. The buyer can retry after correcting the cause or enter/review the quotation manually.

## Privacy and modes

Local inference permits only localhost, loopback and `host.docker.internal` endpoints, disables environment proxies, and does not follow redirects to external services. Normal logs contain stage/model/timing/status metadata rather than supplier text or prices. Raw model responses are retained only by the evaluation runner for the bundled fictional corpus; production extraction diagnostics do not include them.

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
