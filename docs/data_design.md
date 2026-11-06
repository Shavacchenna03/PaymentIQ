# Data Design (Phase 2)

## Scope
- Synthetic data for a fictional UPI fintech called PayFlow.
- Period: 1 April 2026 to 30 September 2026. All timestamps stored in IST.
- Seed: 42. One seeded script regenerates the identical dataset.
- All bank and PSP names are fictional, so no real institution is implied to be unreliable.

## Target volumes
| Table | Volume |
|---|---|
| fact_transactions | about 300,000 attempts |
| dim_customers | 30,000 |
| dim_banks | about 40 |
| dim_psp | 7 |
| dim_failure_codes | about 28 |
| fact_payment_events | about 1,200,000 (about 4 per attempt) |
| fact_reconciliation | one row per attempt |
| retry attempts (subset of fact_transactions) | about 15,000 to 25,000 |

Overall failure rate about 10 percent including customer-side failures. About 0.5 percent PENDING after 24 hours.

## Tables
- dim_banks: bank_id, bank_name, bank_type, size_tier
- dim_psp: psp_id, psp_name, provider_type
- dim_failure_codes: error_code, category, description, retry_class
- dim_customers: customer_id, signup_date, city_tier, primary_device, acquisition_channel. No segment column: segments are discovered in Phase 5.
- fact_transactions: transaction_id, customer_id, payee_id, payee_category, bank_id, psp_id, amount, status, error_code, initiated_at, completed_at, latency_ms, device_type, network_type, channel
- fact_payment_events: event_id, transaction_id, event_type, event_timestamp
- fact_reconciliation: transaction_id, final_status, settled_amount, settlement_time
- truth schema (hidden): transaction_id, intent_id, true_segment, is_duplicate_debit, incident_id. Never queried until the final ground-truth comparison.

## Deferred
- fact_experiments: Phase 8
- dim_date: Phase 3
- journeys view: Phase 5

## Key design decision
There is no journey_id in the raw data. A real company would not have one. Journeys are derived in Phase 5 with SQL (same customer, payee and amount, attempts within 30 minutes), then compared against the hidden true intents to measure how wrong the 30-minute assumption is.

## Build steps
2A schema, 2B dimensions, 2C core simulation, 2D events and reconciliation, 2E quality issues and truth schema, 2F validation and load.
