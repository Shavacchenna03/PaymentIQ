# Assumptions


## Phase 2 assumptions
- Data is fully synthetic. Bank and PSP names are fictional.
- Period: 1 April to 30 September 2026, IST.
- About 300,000 attempts. Overall failure rate about 10 percent. About 0.5 percent PENDING after 24 hours.
- Retry attempts target is about 15,000 to 25,000, not 50,000. Reason: with about 30,000 failures and a 40-50 percent retry rate, 50,000 retries would be unrealistic.
- Generator seed is 42.
- No journey_id in raw data. Journeys are derived in Phase 5.
