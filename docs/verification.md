# Docker verification record

Verified September 9, 2026 on Windows using Docker Desktop 4.56.0, Linux Engine 29.1.3 and Compose. The earlier daemon problem is resolved. Native Accord servers were stopped before testing; ports 3000 and 8000 were served by Docker throughout these checks.

## Final results

| Check | Actual result |
|---|---|
| Docker daemon and Compose configuration | Working Linux engine; valid resolved services, paths, network and volumes |
| `docker compose build --no-cache` | All three application images built, including Node 24/Next.js 16.3.4 and Python 3.12 dependencies |
| Final `down` → `build` → `up -d --wait` | Passed; all five services healthy |
| Fast backend suite inside Linux | **52 passed**, two upstream deprecation warnings; final run 4.22 seconds |
| Live PostgreSQL/Redis/RQ/HTTP suite | **15 passed**, no warnings; final run 8.06 seconds |
| Playwright against Docker | **2 passed**, zero skipped; final run 7.6 seconds |
| ESLint, TypeScript, production build, Ruff | Passed |
| Alembic schema drift | No new upgrade operations detected |
| Fresh PostgreSQL lifecycle | Migration 0001, pgvector, seed, repeat seed and schema check passed |
| Restart persistence | Identical record/file fingerprint before and after recreation; all 35 source files at the final checkpoint verified |

## Services and database

| Service | Verified behavior |
|---|---|
| `db` | PostgreSQL 17, vector extension 0.8.6, pg_isready, named volume, real foreign keys/indexes/Numeric and timezone-aware dates |
| `redis` | Redis 7, PING from API/worker, application enqueue/dequeue, failed-job registry and persistent AOF volume |
| `api` | FastAPI on port 8000; PostgreSQL plus Redis readiness; application process UID 1000 |
| `worker` | RQ 2.12.0 consuming `documents`; same-container process, queue subscription and heartbeat readiness; process UID 1000 |
| `web` | Next.js standalone production server on port 3000; HTTP readiness; same-origin API proxy and session cookies |

API health reports `{"status":"ok","database":"postgresql"}`. Compose sets REQUIRE_POSTGRES=true for API/worker. A negative test with a SQLite DATABASE_URL failed at startup with: `Docker requires a PostgreSQL DATABASE_URL; SQLite fallback is disabled.` No substitute SQLite application database was created.

The initial Docker database was empty. Startup applied the frozen migration and loaded exactly **50 suppliers, 250 items, 2,000 purchases, five RFQs and 20 quotes**. RFQ-1003 contained the expected four suppliers. Reseeding made no changes.

A separate, uniquely named PostgreSQL database independently repeated migration, seed, reseed and schema-drift checks with those exact counts. Its vector extension was verified, then only that temporary database and its temporary source directory were removed. The working database was preserved. Live integration tests also checked foreign-key rejection, CRUD, organization indexes, Decimal retrieval and timezone-aware timestamps.

## Uploads, parsers, OCR and storage

The first Playwright upload run submitted Upload_Atlas_RFQ1003.pdf, Upload_Meridian_RFQ1003.xlsx and Upload_Nova_RFQ1003.csv through the real Inbox. All three were newly queued through Redis, consumed by RQ, parsed and persisted in PostgreSQL, then displayed as Complete in the frontend.

The integration suite verified parser text, SHA-256 fixture lookup, extraction provider `demo`, supplier/item mapping, three line items, Decimal totals and comparison updates. It checked source document IDs, page numbers, source text and confidence. Original bytes fetched through the authenticated API matched the bytes in shared organization-specific storage. Repeated bytes returned 409 without creating another quote. Subsequent browser runs explicitly assert that duplicate branch and existing persisted results; they are not counted as new queued uploads.

Tesseract **5.5.0** executed in the worker container. Both Scanned_Vertex_RFQ1004.png and Scanned_Vertex_RFQ1004.pdf passed actual OCR. The scanned PDF used Poppler rasterization. Both produced text containing Vertex and AX-100 and proceeded into structured quote review. No paid OCR or AI keys were used.

Unknown valid PDFs retained parsed text and finished as Needs Review / Review Required with no fabricated quote. Retrying preserved that behavior. Corrupt PDFs also reached reviewable failure. Traversal-style original filenames were reduced to safe display names; storage used generated IDs under the organization directory. API/worker access through the Windows bind mount worked, and cross-tenant downloads returned 404.

## Failure handling

An explicit integration probe slept five seconds with a one-second RQ timeout. It entered RQ's failed registry; the real callback set its document to Error / Worker failed. Retrying ran through the live worker and reached the expected review state. This deliberately injected failure is distinguishable from an unexplained worker crash.

Redis was deliberately stopped. API readiness returned **503**. A new upload remained saved in PostgreSQL/private storage and showed **Error / Queue unavailable**. After Redis restarted, the existing worker reconnected without manual restart. API readiness returned **200**, and the upload retry finished as Needs Review without a fabricated quote.

Worker stages now appear as structured logs with document ID and stage. Logs contained expected entries from unknown/corrupt files, the timeout probe and Redis outage. Normal startup and buyer workflows showed no recurring migration, permission, proxy or worker failures. Health checks detect unavailability; they are not automatic restart policies.

## RFQ-1003, decisions and security

Before upload revisions, the browser displayed the expected story:

| Supplier | Total | Lead time | Result |
|---|---:|---:|---|
| Atlas Industrial Supply | $127,400 | 36 days | AX-100 increase over the $4.48 historical baseline |
| Meridian Components | $118,980 | 24 days | Best overall |
| Nova Supply Group | $120,200 | 18 days | Fastest delivery |
| Vertex Industrial | $119,850 | 60 days | MOQ/delivery blockers |

Playwright signed in, opened RFQ-1003, inspected source evidence, corrected Meridian's relay price from $4.48 to $4.40, and verified the total changed from **$118,980 to $118,580**. It confirmed review, generated a recommendation, saved/approved an editable email draft, approved the recommendation and inspected the audit entry. The test restored $4.48 afterward. Restoration intentionally stales earlier recommendations; historical approvals remain recorded.

The PostgreSQL integration suite submitted two simultaneous edits with the same version. Exactly one returned **200** and the other **409**. It verified recalculated totals, unchanged original evidence, stale-approval rejection and approval of a fresh reviewed decision. Approval actor and timezone-aware timestamp were checked directly in PostgreSQL. Calculations and ranking remained server-side and deterministic.

Buyer, Admin and Viewer sessions worked through the Next.js proxy with HttpOnly/SameSite Strict cookies. Viewer mutations and Buyer admin-only requests returned 403. The second organization's user could not read the first organization's RFQs, quotes, suppliers, items, documents, files, history or audit data.

Audit filtering passed for QUOTE_UPLOADED, QUOTE_EXTRACTED, FIELD_CORRECTED, SUPPLIER_MATCHED, ITEM_MATCH_CONFIRMED, RECOMMENDATION_GENERATED, RECOMMENDATION_APPROVED and EMAIL_DRAFT_GENERATED. Purchase-history CSV import added a PostgreSQL record; reimport returned 409 without another row. No email, order, payment, ERP write or supplier commitment occurred.

## Browser and restart evidence

Browser verification covered Dashboard, Inbox, RFQs, comparison, Document Review, Suppliers, Items, Purchase History, Audit Log and Settings, including supplier/item details. Desktop screenshots and a 390px mobile view were captured and inspected. No uncaught page errors occurred. Agent-browser independently opened the Docker app and checked browser errors. Selected captures are in `docs/screenshots/`.

The final lifecycle was:

```powershell
docker compose down
docker compose build
docker compose up -d --wait --wait-timeout 90
docker compose ps
```

A fingerprint covered persisted rows (excluding password/session-token hashes) plus every source file's SHA-256. Before and after the cycle, both fingerprints were:

```text
45ec61f63fc9d192bd99212a13caf8bb65ac1a3997ddf2b9b222206499e9da82
```

At that checkpoint, **35 documents/files, 25 quotes, six approvals, six drafts and 2,003 history rows** survived unchanged. See restart-evidence.json for the saved counts and fingerprint. Later tests intentionally added further synthetic review documents/imports and audit entries; these are not duplicate seed records. All key backend, database and browser checks were rerun after this cycle.

## Reproduce

From the repository root, on a running demo Docker stack:

```powershell
docker compose config --quiet
docker compose exec -T -e REQUIRE_REDIS=false -e REDIS_URL=redis://127.0.0.1:1/0 api pytest -q
docker compose exec -T api ruff check .
docker compose exec -T -e RUN_DOCKER_INTEGRATION=true api pytest integration -q
docker compose exec -T api python -m tools.verify_postgres_lifecycle
docker compose exec -T api python -m tools.verify_persistence
```

Fast tests isolate SQLite databases/files and avoid live Redis login counters. The separate integration suite explicitly requires PostgreSQL and uses the real queue. It leaves traceable verification records in the demo database.

From apps/web:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
$env:E2E_UPLOADS='true'
npx.cmd playwright test
```

To repeat the controlled outage on a disposable/demo stack, keep the API container running between these commands:

```powershell
docker compose stop redis
docker compose exec -T api python -m tools.verify_queue_outage down
docker compose start redis
docker compose exec -T api python -m tools.verify_queue_outage recover
```

Always restore Redis even if an assertion fails. README.md documents normal restart and destructive database reset/reseed. The reset path uses the same fresh PostgreSQL lifecycle verified above; the working database's volumes were preserved.

## Fixes and remaining limits

Changes: PostgreSQL-only Docker guard; dependency-aware API health; web/worker health checks; structured worker progress logs; supported RQ Callback API; repeatable browser assertions for revised quotes and duplicate uploads; live integration and lifecycle utilities. Initial test assertion mistakes (`snippet` versus `source_text`, and import 200 versus 201) were corrected to match the existing API contract. No schema rewrite or architecture redesign was needed.

Visual review after uploads exposed a real response-count defect: seven quote revisions were displayed as seven of four supplier responses. RFQ lists and dashboard metrics now count distinct matched suppliers; the showcase says supplier responses. A PostgreSQL regression test verifies four responses and the correct pending-response total while retaining all seven quote revisions for comparison. Final screenshots confirm the corrected counts.

**Optional / unverified:** RTX 5060 container execution, local Ollama/model inference and hosted AI APIs. The GPU Compose override is configured but was not executed. No GPU driver, toolkit or model was installed. Future ERP/email integrations remain outside scope. Real-document extraction accuracy, production load, long-term operations and broader concurrency need separate validation. The fast suite retains two non-failing upstream Starlette/httpx/AnyIO deprecation warnings.
