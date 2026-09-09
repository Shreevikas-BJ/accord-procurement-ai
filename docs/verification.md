# Verification record

Date: September 9, 2026. Host: Windows; Node 24; Python 3.14; local SQLite for executable application verification.

## Checks that passed

- Next.js production build and TypeScript check.
- ESLint and Ruff checks.
- All 52 backend pytest tests passed: Decimal arithmetic/rounding, totals, exact price thresholds, historical windows, missing costs, MOQ/delivery/quantity/UOM/currency/expiration eligibility, scoring, matching, tenant isolation, authorization, input validation, corrections, stale approval rejection, drafts, audit events, source parsing and fixture fallback.
- PDF, XLSX and CSV were uploaded through the real API in isolated integration tests, processed through their actual parser and document pipeline, and retrieved as persisted structured quotes. Queue dispatch was isolated in those tests; this does not constitute Redis/RQ integration verification.
- A clean SQLite database was migrated through the frozen Alembic revision and seeded. Seeding again changed nothing. `alembic check` reported no new operations.
- The critical Playwright browser flow passed against the production standalone server: sign-in → RFQ-1003 → source evidence → relay price correction → save → total recalculation → confirm review → recommendation → edit/approve draft → approve recommendation → verify audit entry. Result: 1 passed; the separate Redis-dependent upload case intentionally skipped.
- Browser navigation covered Dashboard, Inbox, RFQs, supplier comparison, quote review, Supplier Detail, Item Detail, Purchase History, Audit Log and Settings. Screenshots were captured and inspected. A 390px mobile viewport was checked for horizontal overflow.
- No uncaught browser page errors were detected during the passing flow.

The original primary total is $118,980. Correcting Meridian’s AX-100 unit price from $4.48 to $4.40 produces $118,580, a $400 decrease. The test restores $4.48 afterward. Corrections intentionally stale existing recommendations; prior approvals remain in the audit history.

## Host blocker: full Docker verification is pending

Docker Desktop 4.56.0 fails before the Linux engine becomes available:

```text
starting services: initializing Inference manager:
listening on unix://.../Docker/run/dockerInference:
The file cannot be accessed by the system.
```

`docker compose config --quiet` succeeded. `docker compose up --build -d` could not contact `dockerDesktopLinuxEngine`; it did not build or launch the application containers. Native API/frontend verification was performed instead.

This matches reports in Docker’s issue tracker about Windows AF_UNIX runtime sockets, including [docker/desktop-feedback #460](https://github.com/docker/desktop-feedback/issues/460). A narrow attempt preserved the temporary run directory as `run-stale-20260909-accord` and created a fresh runtime directory. Docker recreated the failing socket and crashed again. No Docker containers, images, volumes or configuration were deleted, and no factory reset was attempted.

A working Docker engine—potentially after a host restart or Docker repair—is needed to finish these checks:

1. Build and start all five Compose services from a clean database.
2. Verify PostgreSQL migration and pgvector extension creation.
3. Verify persisted uploads through the real Redis/RQ worker, including retries/timeouts.
4. Run Tesseract against the included PNG and scanned PDF and inspect OCR evidence.
5. Run `E2E_UPLOADS=true` against that stack.
6. Validate PostgreSQL concurrency/locking and Linux bind-mount ownership.

Optional local/hosted inference and RTX 5060 execution were not exercised. Their configuration and error/fallback paths exist; they must not be described as hardware-validated.

## Reproduce

From `apps/api` with dependencies installed:

```bash
python -m pytest -q
python -m ruff check .
```

For a Windows temp-directory permission conflict, use a new directory under the project with `--basetemp=C:/Projects/procurement_ai/.runtime/pytest-check-unique`. Pytest owns and clears that test directory; do not point it at an existing working-data directory.

From `apps/web`, with the API and frontend running:

```bash
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npx playwright test --grep "buyer reviews"
```

The separate upload E2E case intentionally skips unless `E2E_UPLOADS=true`; this prevents a missing queue from being represented as passing upload verification.

The installed Starlette test client currently emits two upstream deprecation warnings concerning httpx/AnyIO. They do not fail the tests; upgrade the test transport when supported by the chosen dependency set.
