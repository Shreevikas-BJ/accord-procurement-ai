# Next milestones

1. Complete the outstanding Linux Docker/PostgreSQL/Redis/Tesseract smoke and concurrency checks. Add automated CI on a clean runner.
2. Pilot the quote-review workflow with three to five procurement teams using anonymized real quotes. Measure corrections and time to a reviewed decision.
3. Benchmark optional local extraction models against the checked-in ground truth and real pilot fixtures; measure field accuracy, latency and review burden.
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
