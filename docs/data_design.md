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


## Schema notes (2A)
- Attempt status is SUCCESS, FAILED or PENDING. INITIATED exists only as an event type.
- staging.stg_transactions has no constraints so deliberately dirty rows (duplicates, UTC timestamps, missing codes) can land there. Cleaning loads the constrained fact_transactions.
- Check constraints enforce cleaning: FAILED rows must have an error_code, SUCCESS and PENDING rows must not.
- true_segment lives in truth.customer_truth because a segment belongs to a customer.
- Timestamps are TIMESTAMP without time zone and always hold IST.
- Indexes are created after bulk load in step 2F.

## Dimensions (2B)
- 40 fictional banks: 8 Large (about 70 percent of volume), 14 Medium (about 22 percent), 18 Small (about 8 percent). Within a tier, volume is shared equally. Any resemblance to a real institution is coincidental.
- Base bank-side failure rate: Large 8 percent, Medium 11 percent, Small 16 percent (worse at peak hours, added in 2C). Calibrated against the 10 percent overall target in 2C.
- Planted roles are stored only in generator/config.py: Tarang National (trap bank), Zenora (hidden bad bank, +0.35 log-odds), Ridgeway (3 outage windows), Clearwave (bad deploy 3 to 16 Aug 2026), QuickRail (UTC timestamps).
- 7 fictional PSPs with volume shares 28, 22, 18, 14, 9, 6, 3 percent.
- 28 failure codes. The database stores five exact retry class names (Safe retry, Customer action, Verify status first, Do not retry, Escalate).
- 30,000 customers, assigned with exact counts and shuffled (not random sampling), so the distributions are exact. Hidden segments live only in truth.customer_truth.
- Customers per segment: Reliable 13,500, Retry-dependent 6,000, Failure-prone 3,600, Abandoning 3,900, High-value 3,000.

## Intents (2C-1)
- 280,000 intents: 271,600 base intents plus 8,400 deliberate repeat intents (3 percent). Retries add about 20,000 attempts later.
- Daily volume = linear growth of 35 percent over the period, times a weekday pattern, times a 15 percent month-end bump. Hourly volume has morning, lunch and strong 8-10pm peaks.
- Customers transact only after their signup date. Customer activity is lognormal, so some customers transact far more than others.
- Each customer has a primary bank (used 85 percent of the time) and a secondary bank. Bank weights follow tier volume share, tilted by city tier and rescaled so each bank's overall share is unchanged. Tarang National skews to Tier 3 customers and Zenora to Tier 1 customers (P4).
- Network depends on city tier. Amount is lognormal by payee category, 2.5 times larger for High-value customers, and 0.6 times for Zenora transactions.
- Repeat trap: each repeat copies an earlier intent (same customer, payee, amount, bank) 5 to 45 minutes later. About 75 percent fall within the 30-minute window and will be wrongly merged by journey logic in Phase 5. The real link is stored as repeat_of_intent_id.
- Intents are saved to data/raw/intents.csv (gitignored). Failures, latency, status and retries come in 2C-2 and 2C-3.

## Failure model (2C-2)
- Each first attempt gets a probability for each failure family: bank, network, customer, PSP, risk, technical, unknown, three limit rules, the bank outage and the PSP bad deploy. Each family fires independently. If several fire, one is chosen in proportion to its probability, then a code is drawn within the family.
- Four families are calibrated by a single constant each so their mean probability hits a target: network 4.0 percent, bank 2.0 percent, customer 1.8 percent, PSP 1.0 percent. Risk, technical, unknown, limits and incidents add about 1.2 percent. The overall target is about 10 percent.
- Network is the largest family, so the weak-network confound behind the Simpson's trap (P4) is visible. Revised from the first estimate of bank 3.5 and network 2.
- Outage bank changed from Ridgeway (Medium, too few payments in the windows) to Kestrel Commercial (Large). Windows: 14 May 11:00-15:00, 22 Jul 18:00-23:00, 9 Sep 08:00-12:00. Ridgeway no longer has a planted role.
- Failures fall by 0.15 log-odds over the period (P13) and rise 0.12 log-odds at month-end.
- BNK_03 (insufficient funds) is generated by the customer family even though its category is Bank-side.
- Outputs data/raw/first_attempts.csv and data/raw/failure_truth.csv (true probabilities and incident ids). Both are gitignored.

## Latency, pending and debited flag (2C-3a)
- Latency is in milliseconds. SUCCESS has a lognormal latency with median 1,800 ms, scaled by network (WiFi 0.85, 5G 0.80, 4G 1.0, 3G 1.8, 2G 2.8) and bank size (Large 1.0, Medium 1.1, Small 1.25).
- Failures have code-specific latency. Timeouts are long by definition: NET_01 about 30 s, NET_03 about 20 s, NET_02 about 8 s, BNK_04 about 12 s. Quick failures such as wrong PIN (CUS_01) are about 1.2 s.
- Clearwave bad deploy (P7): latency of non-timeout attempts ramps linearly from 1.0x on 3 Aug to 2.0x on 16 Aug, then returns to normal on 17 Aug.
- PENDING after 24 hours is about 0.5 percent of attempts. It is created from 6 percent of failures with uncertain-status codes (NET_01, NET_02, NET_03, BNK_04, UNK_02) and 0.25 percent of successes. PENDING rows have no error code, no latency and no completion time.
- is_debited (P12) marks 3 percent of timeout failures (NET_01, NET_02, NET_03 still FAILED) where the customer was really debited. It exists only in data/raw/attempt_truth_first.csv.
- Outputs: data/raw/attempts_first.csv and data/raw/attempt_truth_first.csv (both gitignored). Retries come in 2C-3b.
