# Assumptions


## Phase 2 assumptions
- Data is fully synthetic. Bank and PSP names are fictional.
- Period: 1 April to 30 September 2026, IST.
- About 300,000 attempts. Overall failure rate about 10 percent. About 0.5 percent PENDING after 24 hours.
- Retry attempts target is about 15,000 to 25,000, not 50,000. Reason: with about 30,000 failures and a 40-50 percent retry rate, 50,000 retries would be unrealistic.
- Generator seed is 42.
- No journey_id in raw data. Journeys are derived in Phase 5.

## Phase 2C-3a assumptions
- Duplicate-debit probability is 3 percent of timeout failures. This is inflated from 1 percent for statistical power and is not a real-world rate.
- PENDING after 24 hours is about 0.5 percent: 6 percent of failures with uncertain-status codes and 0.25 percent of successes.
- Success latency median is 1,800 ms. Failure latencies are code-specific (see config LATENCY_CODE).
- LIM_01 (daily limit exceeded) is accepted as negligible (4 failures) because few customers reach 1 lakh rupees in a day at the generated amounts.
