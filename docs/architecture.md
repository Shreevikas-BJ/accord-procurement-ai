# Procurement rules and implementation boundaries

## Data and ownership

The schema separates organizations, users/sessions, suppliers/contacts, items/aliases/mappings, RFQs/requirements, documents/extractions, quotes/lines, purchase history, recommendations, alerts, drafts, approvals, corrections and audit events. Tenant-owned records contain `organization_id`. UUIDs, indexes, uniqueness constraints and foreign keys enforce ordinary relational integrity. API authorization checks tenant ownership of all supplied foreign IDs; database row-level security is a future defense-in-depth measure.

JSON is used for source evidence, raw validated extraction, price tiers, audit differences and immutable recommendation snapshots. Quote lines and purchase history remain normalized relational rows. The initial Alembic revision contains frozen table operations rather than importing live application metadata at migration time.

## Financial rules

- `Decimal` is used from validation through calculations and persistence; API monetary values serialize as strings.
- Line totals are quantity × selected unit price, rounded half-up to two decimals. The subtotal sums rounded lines. Evaluated total adds shipping and tax.
- Unknown price/quantity/shipping/tax produces an unknown evaluated total, never an assumed zero.
- Supplier-stated line/subtotal/total values remain editable source data. They are reconciled against calculated totals and discrepancies block recommendations.
- History uses purchases dated on or before the quote date, matching internal item, currency and UOM. The six-month window is 183 days; three months is 92 days. Averages are unweighted means of unit prices.
- Price change is `(current - average) / average`; no percentage is returned for a zero/missing baseline. The exact, unrounded Decimal change is compared using `>=` to the configured threshold.
- No FX or UOM conversions are invented. Currency mismatch, inconsistent scope, or quantity/UOM differences prevent like-for-like comparison.
- Quantity-tier pricing must match exactly one applicable range and its selected unit price. Overlapping or inapplicable tiers require review.
- Savings = highest complete comparable total − recommended total, clamped to zero. This is potential savings, not realized savings.

## Matching

Supplier matching prioritizes exact normalized names, known aliases, then email domain. Ambiguous identity remains unmatched. Human confirmation can add a supplier alias.

Item matching uses exact normalized internal SKU, manufacturer part number, persisted supplier-specific mapping, then known aliases. Fuzzy description similarity returns three suggestions but never silently chooses a substitute. A buyer can create a new internal item and confirm the mapping. Confirmed mappings are stored for subsequent quotes from that supplier.

## Dates and scoring

Lead-time ranges use the largest calendar-day value (`4–5 weeks` → 35 days). Explicit delivery dates take priority; otherwise projected delivery begins at the current evaluation date. Expired offers cannot be recommended. There is no business-day calendar, transit calendar, incoterm cost model, or FX provider in this MVP.

Default weights are price 50, lead time 25, reliability 15 and fit 10. Weights must sum to 100. Individual factors are rounded to two decimal points, then summed:

| Factor | Rule |
|---|---|
| Price | `min(1, lowest comparable total / quote total) × weight`; a complete zero-total quote receives the full price factor |
| Lead time | `min(1, (fastest comparable days + 1) / (quote days + 1)) × weight`; missing lead time receives zero |
| Reliability | On-time fraction of completed historical purchases for relevant RFQ items × weight; no history uses an explicitly disclosed neutral 50% |
| Fit | Full weight if all critical requirements pass; otherwise zero |

The plus-one lead-time convention handles same-day offers and prevents division by zero. Factor ratios are capped to preserve the 0–100 score range. Different currencies have no score. Eligible candidates are ordered by descending score, then ascending cost, then supplier name for deterministic ties.

Missing/uncertain identity, scope, cost, price, MOQ, lead time, mismatched quantities/UOMs, total discrepancies, expiration, late delivery and duplicate quote numbers are eligibility blockers. Price increases are warnings: price history alone does not automatically disqualify a supplier. Low-confidence extraction is a blocker until a human explicitly confirms review; original confidence/evidence is preserved in the audit record.

## Trust and decisions

Every correction stores original/current values, actor and timestamp. Source evidence remains immutable. Saving a review increments the quote version and RFQ revision and refreshes alerts. Weight/history changes also invalidate prior recommendations. Recommendation snapshots retain input quotations, factor scores, weights, explanation and evaluated date.

Approval takes a lock on the RFQ in PostgreSQL, checks the latest revision and currently recommended supplier, requires a reviewed quotation, then records the decision and audit event. Approval is internal only. It never changes the RFQ to an externally awarded purchase, sends supplier messages, or creates a purchase order. Later corrections mark even previously approved snapshots stale while preserving their historical approval event.

The application does not automatically normalize supplier promises into legal commitments. Drafts use deterministic templates and stored findings. A buyer can choose negotiation, missing-information, updated-lead-time, revised-pricing or follow-up intent.

## Pipeline and failure boundaries

`StorageProvider`, `DocumentParser`, `OCRProvider`, `AIProvider`, and `EmailProvider` are explicit interfaces. Local filesystem, Tesseract, supported file parsers, demo extraction and OpenAI-compatible inference are implemented. Cloud storage/OCR and actual email delivery are future adapters.

The RQ job is capped at five minutes. Individual OCR/model subprocesses have shorter timeouts. Processing stages are committed between steps. Result persistence rechecks document uniqueness. Queue errors, parser errors and model failures are visible; an RQ failure callback marks unhandled timeouts as retryable errors. A worker crash that prevents any callback can still require operator intervention; a heartbeat/reconciliation service is a future reliability improvement.

A provider cannot alter application controls. It receives a JSON schema and untrusted source text, with no tools or action permissions. Pydantic rejects malformed structures and invalid numeric ranges. Unsupported source snippets are downgraded in confidence. This is a bounded extraction interface, not a general autonomous agent.

## Operational limitations

- PostgreSQL migrations/pgvector, simultaneous quote-edit conflict handling, non-root API/worker file access, Redis/RQ integration and image/scanned-PDF OCR have passed live Docker checks. This covers the tested local workflows, not production-scale concurrency or load. See verification.md.
- No production SSO/MFA, password reset, user deactivation UI, database RLS, malware scanning, secrets manager or production deployment is included.
- Login throttling uses Redis when reachable and currently fails open when Redis is unavailable; use a strict gateway policy before public exposure.
- CSV import is all-or-nothing for application validation and conflicts, with a 10,000-row cap. Large imports are synchronous; move to a background job before scaling.
- Lists paginate, but catalogs and comparison history still assume MVP-sized organizations. Broader load tests and query optimization are needed before large datasets.
- RFQ creation/invitation administration, supplier onboarding, split awards, generic semantic matching and configurable business calendars are future work. Seeded RFQs support the complete quote-to-decision workflow now.
- Source bounding boxes are modeled but not drawn; scanned sources need readable OCR and original-page review.
- A three-letter uppercase currency code is validated syntactically; there is no external currency registry or rate feed.
