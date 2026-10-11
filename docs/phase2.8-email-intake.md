# Phase 2.8 — local procurement email intake

Phase 2.8 adds local procurement-email ingestion to Accord. A buyer can paste an email or import an `.eml` file, preserve its headers/body/attachments, identify the sender safely, associate it with an RFQ, reconcile quote facts across the message and supported attachments, and review the resulting quote with field-level evidence. Email is never sent and no mailbox account is connected.

The implementation is complete and the safety gates passed, but the untouched final holdout missed the required extraction and evidence targets. The email-intake workflow is **NOT READY for limited supervised use**. Keep it in development until the parser generalization gaps below pass a new independent holdout.

## Frozen boundary

| Component | Version / configuration |
|---|---|
| Email prompt | `email-intake-2.8.0` |
| Email pipeline | `local-email-2.8.0` |
| Document prompt / pipeline | `quote-v4` / `local-2.7.0` |
| Optional local model | `qwen2.5vl:7b`, digest `5ced39dfa4ba…`, Ollama 0.30.11 |
| Supported intake | Pasted message, `.eml`, HTML-only and multipart email |
| Supported attachments | Digital PDF, XLSX, CSV, TXT |
| Deferred attachments | Scanned/image-only PDF, JPG, PNG |
| External mailbox / delivery | Deferred; no Gmail, Outlook, IMAP, Graph, or email sending |

Deterministic parsing and matching handle ordinary email facts first. Qwen is optional and runs only in local mode when deterministic extraction does not find a quote. Detected prompt-injection text prevents that model call. The model has no tools, database authority, email capability, or purchasing authority.

## Architecture and data model

The API accepts multipart `.eml`, pasted email fields, and pasted email plus attachments. It validates size and type, computes content hashes, stores private files under the tenant upload path, persists the email, and enqueues the `documents` RQ queue. The worker parses and reconciles the message, attachment documents, supplier/RFQ identity, current quote, revisions, conflicts, evidence, and audit events in one tenant-scoped database transaction.

Phase 2.8 adds these tables:

- `email_threads`: normalized subject, supplier/RFQ association, first/last message times, current email and current quote.
- `procurement_emails`: RFC identifiers and references, participants, clean body, quoted history, signature, classification, sender role, match state, hashes, processing state, and provenance.
- `email_attachments`: filename, MIME type, size, SHA-256, private storage path, linked document, supported/deferred state, and processing error.
- `email_evidence`: field value and exact source text plus email/message/attachment/document location and acceptance decision.
- `supplier_match_candidates`: reviewable possible duplicates and their method/score; candidates never auto-merge.
- `email_field_conflicts`: competing body/attachment values and explicit resolution state.
- `quote_revisions`: immutable effective-quote snapshots tied to the source email and thread.

Suppliers and contacts also retain normalized identity, source email provenance, and whether the row was auto-created. Migration `0003_email_intake` upgrades existing PostgreSQL data in place and creates tenant indexes. The frozen initial migration was not regenerated.

## Parsing and normalization

The `.eml` parser uses Python's standard email package. It supports folded/RFC-encoded headers, multipart alternatives, text and HTML bodies, HTML-only email, RFC `Message-ID`, `In-Reply-To`, `References`, sender/recipient addresses, and sent timestamps. It strips ordinary reply prefixes from thread subjects, separates signatures and quoted history, normalizes whitespace, and bounds retained content.

HTML is converted to readable text without executing remote content. HTML tables become structured rows before extraction. The current message remains separate from quoted prior messages so stale values cannot silently replace the latest supplier statement. Buyer-sent messages are classified separately and cannot become supplier commitments.

The message classifier distinguishes quote, quote revision, negotiation response, acknowledgement, clarification, decline, and other mail. Revision phrases and RFC references join timelines. Subject/RFQ/quote identifiers require explicit procurement-shaped values; prose words are not accepted as quote numbers.

## Supplier matching and creation

Supplier identification follows this order:

1. exact normalized supplier-contact email;
2. exact verified non-generic email domain;
3. known supplier alias;
4. exact normalized supplier name;
5. reviewable fuzzy possible duplicate;
6. new `NEW_UNVERIFIED` supplier.

Generic and personal domains such as Gmail or Yahoo never establish an automatic domain match. Ambiguous contact/domain identity cannot auto-link. Fuzzy matches remain `POSSIBLE_EXISTING_SUPPLIER` candidates for buyer resolution. A safe new supplier records the source email and creates a provenance-linked contact; it cannot become verified without an explicit buyer action. Buyer-domain senders are labeled `BUYER` and do not create suppliers.

The final holdout produced zero wrong automatic links and safely created ten new unverified suppliers. One alias case and one fuzzy duplicate-risk case were missed because a generic-domain signature exposed `Tender Desk` instead of the organization name. These are false negatives that require review, not wrong links.

## RFQ, attachment, conflict, and revision rules

RFQs match on normalized explicit identifiers in the subject or current body and remain tenant scoped. Attachments reuse the existing document parser and are deduplicated by SHA-256. A previously stored document may be linked without duplicating bytes. Unsupported images and image-only PDFs remain preserved with `UNSUPPORTED_ATTACHMENT_FOR_CURRENT_PHASE` and a reviewable explanation.

Reconciliation keeps every source candidate. An explicitly revised attachment may outrank the body; otherwise a disagreement creates an `email_field_conflicts` row and requires review. Missing fields stay missing. Accepted values keep exact source records. Buyer confirmation writes a new decision and audit event without mutating the original evidence.

RFC references take priority for thread grouping. When references are unavailable, the normalized subject plus supplier/RFQ and a bounded time window provide the fallback. A revision produces an immutable snapshot before updating the current effective quote. Older quotes and source values remain in the timeline.

Conditional negotiation language is represented as candidate tiers or review-required evidence. A buyer request is not treated as a supplier offer. Shipping, tax, currency, MOQ, lead time, and payment terms require explicit source language; missing costs never become zero.

## Security and privacy

- Email data and attachments remain on the local filesystem, PostgreSQL, Redis, and optional local Ollama endpoint.
- Tenant filters cover every email, thread, attachment, candidate, conflict, revision, evidence, file download, and mutation.
- Import requires Buyer/Admin role; Viewer stays read-only.
- MIME/extension, content size, PDF encryption/text presence, spreadsheet expansion, and parser bounds are enforced.
- Prompt-like supplier text is untrusted data. Imperative injection lines are excluded from accepted extraction, and detected injection disables optional Qwen processing.
- No endpoint sends email, connects a mailbox, creates a purchase order, or approves a sourcing decision.
- Successful authentication now clears its Redis throttle key; failed sign-ins continue to accumulate toward the five-minute limit.

## Benchmark protocol

The development corpus contains 100 synthetic but realistic emails: plain text, HTML tables, attachments, revisions, negotiations, buyer messages, new suppliers, possible duplicates, conflicts, quoted history, and prompt-injection cases. It was used for implementation.

The first 40-case holdout exposed unsafe prompt-injection handling, permissive quote-number parsing, and supplier identity gaps. Those results are preserved in `benchmark-data/results/phase28-email-holdout`. Only the safety defects were repaired. A separate 40-case final holdout was then generated, hashed, committed, run once, and never used for tuning. Its results are preserved in `benchmark-data/results/phase28-email-holdout-final`.

### Development results

All reported development accuracy metrics were 100%, with 100% processing success and accepted-evidence match. There were zero wrong automatic supplier links, unsupported accepted critical values, critical error escapes, missing-field hallucinations, or accepted prompt-injection manipulations. Twenty-six suppliers were safely auto-created as `NEW_UNVERIFIED`. Median latency was 0.0023 seconds for email-only cases and 0.0071 seconds for email plus attachment; p95 was 0.0100 seconds.

### Untouched final holdout

| Metric | Result |
|---|---:|
| Supplier overall | 95.000% |
| Exact contact email | 100.000% |
| Verified domain | 100.000% |
| Known alias | 80.000% |
| Normalized name | 100.000% |
| New supplier | 100.000% |
| Possible duplicate risk | 80.000% |
| RFQ | 100.000% |
| Quote number | 100.000% |
| SKU | 90.000% |
| Quantity | 90.000% |
| Unit price | 82.500% |
| Currency | 100.000% |
| MOQ | 90.000% |
| Lead time | 100.000% |
| Payment terms | 100.000% |
| Shipping | 100.000% |
| Tax | 100.000% |
| Critical extraction | 86.842% |
| Complete attachment-case reconciliation | 78.947% (15/19) |
| Conflict detection | 100.000% |
| Thread grouping | 100.000% |
| Revision/current-effective-quote resolution | 100.000% |
| Buyer/supplier separation | 100.000% |
| Processing success | 100.000% |
| Accepted evidence match | 95.739% |

Safety counts were zero wrong automatic links, zero unsupported accepted critical values, zero critical-error escapes, zero missing-field hallucinations, and zero accepted prompt-injection manipulations. Ten new suppliers were safely created. Median latency was 0.0069 seconds for email-only and 0.0127 seconds for email plus attachment; p95 was 0.0163 seconds.

Four digital-PDF attachment cases selected a boilerplate `Selectable-text` token as the SKU and missed the actual commercial row, quantity, unit price, and MOQ. Three negotiation sentences using “Best we can do is $87.125” omitted unit price. One alias case and one possible-duplicate case failed to recover the organization identity from a generic-domain signature. Evidence misses came from normalized supplier names derived from domains or headers rather than literal source spans. No missed case produced a wrong automatic link or an accepted unsupported critical value.

## Verification completed October 10, 2026

- 165 fast backend tests passed after the authentication regression test was added; Ruff passed.
- 15/15 live Docker/PostgreSQL/Redis/RQ integration tests passed.
- Existing PostgreSQL upgraded to `0003_email_intake`; Alembic reported no drift.
- Fresh PostgreSQL lifecycle, exact seed counts, and idempotent reseeding passed.
- A full API/worker/web recreation preserved the imported email, linked RFQ/quote, status, and 12 evidence records.
- Real Qwen checks finished with 5 passed and 2 strict expected failures. Baseline text inference, PDF, XLSX, and revised email passed. The email-only case omitted an alphanumeric RFQ identifier; the negotiation case extracted quantity/price but omitted SKU.
- The new Playwright email flow passed from `.eml` import through worker processing, detail rendering, field confirmation, RFQ comparison, and audit lookup. The established buyer decision workflow also passed.
- The production Next.js build, TypeScript, ESLint, and backend Ruff checks passed.
- All five Compose services finished healthy. Port 8001 was used for the host API because an unrelated local service owned 8000; the Docker network still used `api:8000`. The web app used its approved `localhost:3000` origin.

## Readiness and next phase

The safety boundary is strong: no wrong auto-links, no critical escape, no accepted prompt-injection manipulation, correct conflict detection, correct revision resolution, and safe new-supplier creation. Readiness still fails because critical extraction is 86.842%, unit price is 82.500%, attachment-case reconciliation is 78.947%, alias and duplicate-risk matching are 80%, and accepted evidence match is 95.739% rather than 100%.

Accord is therefore **NOT READY for limited supervised email-intake use**.

The recommended next phase is **Phase 2.9 — email parser generalization and a second supervised-readiness gate**. Fix PDF commercial-row selection, negotiation-price phrasing, generic-domain signature identity, and literal supplier-identity evidence on a new development set. Then freeze the code and run a new untouched holdout. Do not tune against or rerun the Phase 2.8 final holdout. Gmail/Outlook ingestion, scanned/image attachment work, email delivery, purchase orders, ERP integration, and other automation remain outside that phase.

## Artifacts

- [Development manifest](../benchmark-data/phase28-email-development/manifest.json) and [results](../benchmark-data/results/phase28-email-development/summary.json)
- [First holdout](../benchmark-data/results/phase28-email-holdout/summary.json), retained as safety-repair evidence
- [Final holdout manifest](../benchmark-data/phase28-email-holdout-final/manifest.json), [integrity file](../benchmark-data/phase28-email-holdout-final/MANIFEST.sha256), and [results](../benchmark-data/results/phase28-email-holdout-final/summary.json)
- [Benchmark generator](../tools/phase28/generate_corpus.py) and [evaluator](../tools/phase28/evaluate_email_corpus.py)
- [Demo revised email](../demo-data/emails/Atlas_RFQ1003_Revised.eml)

