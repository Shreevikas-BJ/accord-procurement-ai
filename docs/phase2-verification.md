# Phase 2 verification evidence

The acceptance flow is browser upload → same-origin API → private source storage → Redis/RQ → parsing/OCR → actual local Qwen → validation → PostgreSQL → buyer review. Automated benchmark runs use no application database.

The implementation and verification work below is delivered, but not every Phase 2 acceptance condition is satisfied. In particular, the real model still invents some absent values and follows some embedded extraction instructions. Review flags contain the observed cases; they do not establish reliable null behavior or instruction resistance. The benchmark report records these remaining accuracy failures, and this is not a claim of full Phase 2 or buyer-pilot readiness.

## Executed checks

| Check | Result |
|---|---|
| Fast backend suite, isolated SQLite/Redis disabled | 85 passed; includes the original 52 tests and 33 local extraction/persistence regressions |
| Live Docker integration suite | 15 passed against PostgreSQL, Redis, RQ and HTTP through the web proxy |
| Fresh PostgreSQL lifecycle | Migration `0002_local_extraction`, schema comparison, seed and idempotent reseed passed |
| Existing Playwright decision and upload flows | 2 passed in demo mode, with live uploads enabled |
| Opt-in real Ollama checks | 2 passed: exact installed model availability and an unknown Cedar quotation |
| Local five-format Playwright flow | 1 passed: PDF, scanned PDF, PNG, XLSX and CSV, with real review/correction assertions |
| Read-only local workflow proof | PASS for five formats, source hashes, supplier/item matching, original AI lineage and zero evaluation approvals/history |
| Backend lint | Ruff passed |
| Frontend TypeScript, lint and production build | Passed; production build also passed inside Docker |
| Full Docker restart and persistence | Passed: all five services healthy, 50 source-file hashes verified, identical business-row fingerprint before and after restart |

Frontend typecheck, lint and production build are also run as part of final verification. Two dependency deprecation warnings remain in the fast test runner (Starlette/httpx and anyio); no failing backend tests are hidden. Live tests intentionally create unknown/corrupt/timeout probe documents and expected failure logs in the demo tenant. The local workflow produces no supplier messages or purchase commitments.

The live schema test originally pinned migration `0001`; it now checks the repository's Alembic head. The existing browser upload test now uses Inbox search to find historical duplicate uploads after pagination. Neither change removes a product assertion. Local browser test timing was corrected to wait for the actual save response, not an earlier success notice.

## Real local workflow

[Machine-readable proof](local-workflow-evidence.json) contains document/quote IDs, source SHA verification, model/prompt/pipeline versions, original and current supplier names, corrected fields, actors and timestamps. It is restricted to bundled fictional evaluation data.

- Digital PDF: `synthetic-001-standard_table.pdf`, text path, actual model output saved in PostgreSQL. Qwen omitted shipping/tax; the buyer entered the printed 12/0. Changing 20 units from 1.25 to 1.35 produced a 39.00 total, then restoring 1.25 produced 37.00. Original AI price 1.25 remains in every correction's provenance.
- Scanned PDF: `synthetic-002-supplier_sku_and_mpn.scan.pdf`, OCR plus selected-page vision, source-page evidence and matched item records.
- PNG: `synthetic-003-comma_thousands.png`, OCR plus vision. The buyer corrected `J uniper Motion Systems` to `Juniper Motion Systems`; the original OCR/model value remains immutable in the extraction and correction provenance.
- XLSX: `synthetic-005-lead_time_range-v21.xlsx`, deterministic spreadsheet parsing and semantic model extraction. Its vertical label/value rows now yield exact price evidence with sheet and row information. An earlier extraction with missing evidence is preserved as a separate evaluation document.
- CSV: `synthetic-006-weeks.csv`, deterministic cell parsing and semantic model extraction, with verified price evidence.

The final UI pass reused three already processed documents via expected HTTP 409 duplicate handling and created the revised XLSX and CSV with HTTP 202. The earlier attempts had actually enqueued and processed the PDF, scan and PNG. Consequently the lab has six documents (five verified formats plus the preserved earlier XLSX), rather than claiming five fresh uploads in the final pass.

The first three documents retain their original `local-2` extraction version. The revised spreadsheet and CSV use `local-2.1`. All use actual `qwen2.5vl:7b`, `quote-v2`, provider `local`, and `fallback=false`. The separate final corpus run covers all 100 documents on `local-2.1`.

The original model omitted costs in all five UI examples. Entering two costs and correcting one supplier name demonstrates the workflow; it does not turn those original extractions into complete/correct model answers. Test price edits, reversions and retries add audit entries, so their count is not an estimate of natural buyer correction effort.

## Tenant and source preservation

Before evaluation setup, Apex had 44 documents and 2,006 purchase-history rows. Read-only verification after the UI work reports the same counts. Accord Evaluation Lab has zero purchase-history rows and zero approvals. The 100-document benchmark does not seed or write any tenant. All six evaluation source files are retained; source hashes were checked for the five acceptance files.

The persistence fingerprint also checks every stored document's hash and fingerprints all business rows while excluding password/session-token hashes. The full Docker stack was restarted successfully: [before](phase2-persistence-before.json) and [after](phase2-persistence-after.json) records have identical counts and fingerprint, with all 50 source files verified. All five services returned healthy with local mode configured. A changed fingerprint must be investigated, not silently accepted.

## Visual evidence

- [Local settings and Ollama availability](screenshots/local-settings.png)
- [Loaded scanned-PDF preview](screenshots/local-pdf-preview.png)
- [Spreadsheet source evidence](screenshots/local-spreadsheet-evidence.png)
- [Buyer price correction](screenshots/local-price-correction.png)

The browser tests capture JavaScript page errors and assert none. The real browser Settings inspection showed LOCAL AI, `qwen2.5vl:7b`, and `Ollama · Available`. Source panels expose missing/visual evidence rather than invented quotations. See [benchmark limitations and failures](extraction-benchmark.md) before interpreting a successful workflow as extraction accuracy.

The loaded native PDF viewer was inspected separately after network idle; it displayed the original two-page scanned quotation. Immediate headless full-page screenshots can capture the PDF area before its viewer paints, so the saved loaded-viewer screenshot is the visual proof for PDF preview.

The final read-only [RFQ-1003 comparison](phase2-rfq1003.json) still recommends Meridian at 118,980.00 and 94/100; Nova is fastest and Vertex remains ineligible. Revised demo uploads have the same supplier totals and do not introduce evaluation-tenant quotes into Apex.
