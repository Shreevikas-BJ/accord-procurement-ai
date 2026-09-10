# Next milestones

1. Add automated Linux CI for the now-verified Docker/PostgreSQL/Redis/Tesseract stack, including the opt-in integration suite and browser workflows.
2. Test the benchmarked local Qwen extractor on an independent set of anonymized supplier documents. Prioritize omitted costs, instruction contamination, duplicate rows and lead-time/date errors from [Phase 2](extraction-benchmark.md).
3. Decide whether to start a supervised three-to-five buyer pilot after reviewing independent accuracy and correction effort. The synthetic benchmark alone does not establish pilot readiness; no pilot is launched in Phase 2.
4. Add RFQ creation/invitation management and supplier onboarding, richer manual entry, extraction bounding-box highlights, background imports and reliable queue reconciliation.
5. Add Gmail/Outlook intake only when users validate the workflow; select one ERP integration based on actual customer demand, then expand.

## Five questions for procurement users

1. Does the comparison reflect the actual buying decision, including freight, tax, quantities, UOM, tiers and delivery promises?
2. Can a buyer quickly verify or correct the important fields, and does the source evidence justify the displayed confidence?
3. Are the scoring weights, history baseline, anomaly threshold and eligibility blockers understandable and acceptable?
4. Does the recommendation/email/approval workflow save time without encouraging accidental supplier commitments?
5. What are the most frequent quotation formats and missing fields, and what percentage of real RFQs need split awards or non-price exceptions?

## Intentionally postponed

No SAP/Oracle/NetSuite/Coupa/Dynamics integration, real outbound email, purchase-order creation, payments, supplier discovery/marketplace, autonomous negotiation, contract management, inventory or demand forecasting, shipment tracking, accounting integration, enterprise multi-stage approvals, native mobile app, Slack/Teams, custom model training, Kubernetes, Kafka or production cloud infrastructure.

Those capabilities should follow evidence from the focused quote-analysis product, not precede it.
