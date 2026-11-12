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

## Phase 2C-3b assumptions
- Retry volume is about 12,000 to 16,000, not 20,000. The retry rates were not inflated to reach the target.
- Retry rates and success rates by error group are assumptions, not industry statistics.
- Pending first attempts are retried 40 percent of the time. These are the realistic duplicate-payment scenario because the customer sees no answer.
- Duplicate debits come from debited timeouts (3 percent, inflated) and from PENDING attempts that were really successful. Both exist only in the truth files.
- CUS_04, CUS_05 and BNK_05 form a "customer other" retry group (30 percent retry, 50 percent success) because the first retry table did not cover them.
- The Clearwave latency ramp is not applied to retries.

## Phase 2D assumptions
- Data extract date is 5 Oct 2026 at 00:00. Every attempt is more than 24 hours old, so the 24-hour settlement lag rule excludes no attempts.
- Event timestamps are synthetic, placed at fixed fractions of the attempt duration. They are not real network measurements.
- Reconciliation mismatch rates (0.1 percent reversals, 0.5 percent failed-but-settled) are assumptions, not industry statistics.
- 80 percent of PENDING attempts resolve by the extract date. This is an assumption.
- FAILED rows have no settlement_time because no money settled.

## Phase 2E assumptions
- Data quality issue rates (0.2 percent missing latency, 0.3 percent missing error code, 0.1 percent duplicates) are assumptions, not industry statistics.
- QuickRail is the only PSP writing UTC timestamps. The offset is exactly 5 hours 30 minutes.
- Duplicate rows are exact copies. Real duplicates sometimes differ slightly, which is not modelled.
- Reconciliation timestamps come from the bank and are always in IST.

## Phase 2F-1 assumptions
- Latency recovery is (completed_at minus initiated_at) plus 500 ms. The diagnosis showed the error is within 500 ms for about 97 percent of rows and up to about 1.3 seconds in the worst case, probably on retry rows that start at a fractional second.
- FAILED rows with no error code become UNK_01. This can hide the true cause, including "Do not retry" codes. These rows are listed in reports/dq_fixed_rows.csv and should be excluded from root-cause analysis by code.
- Only exact duplicates are removed. If copies ever differed, the script stops.


## Phase 3B assumptions
- The 30-minute first-attempt rule is imperfect: 5,171 repeat purchases are misread as retries and 679 late retries are misread as first attempts (measured in 3A).
- Weekly trend analysis uses full 7-day weeks only. The first and last weeks of the period are partial and are excluded.
- Month lengths are equal for April and September (30 days), so the two can be compared directly.


## Phase 3E limitations
- The latency regression removed failures with slow-by-design codes but kept all successes. This biases the model: slow attempts look like failures, and the 2G odds ratio came out below 1. The result is reported as a cautionary example, not as a finding.
- The change-point search uses a likelihood ratio that is not chi-square distributed, so significance comes from a permutation test (200 shuffles). With 200 shuffles the smallest possible p-value is about 0.005.
- The Small-bank cell at or above Rs 10,000 has only 503 attempts, so the 90 percent failure rate is approximate.

## Phase 6 assumptions
- Value unit is the w30b journey amount (the intended payment). Journeys starting with a do-not-retry code (CUS_03, TEC_01, RSK_01) are excluded from recovery value, as in the metric dictionary.
- Transaction value is not revenue. Revenue at risk will use a take rate of 0.5 percent of value as a labelled assumption, with 0.3 and 1.0 percent as a sensitivity range. These are not PayFlow facts.
- Derived journeys misstate value slightly (346 merged and about 676 split under w30b). Check 09 measures the gap against the hidden intents.
- Scenarios (2, 5 and 10 point recovery gains) are hypothetical, not achieved results.

## Phase 7 assumptions
- The rules layer is a decision table built from retry classes, status certainty and a bank-incident hold. It is decision support, not a live payment engine.
- The incident hold uses same-block hindsight (bank and 3-hour block, at least 15 attempts, Wilson lower bound above 20 percent). A live system would need a trailing window and would detect incidents later.
- The duplicate-debit detector uses observable data only (app status and bank reconciliation inside a w30b journey). Truth columns are read only to score it.
- Observed recovery by decision comes from customers who chose to retry. It is not what a system-triggered retry would achieve. Phase 8 tests that.

## Phase 7-2 assumptions
- Model trained on April to July, tested on August to September. The test period contains the Clearwave incident and the August to September outage windows, so it is harder than a random split.
- prior_retry_rate mostly reflects whether a customer retries. It is not evidence that a system-triggered retry would work.
- The policy simulation assumes a system retry succeeds at the observed retry success rate of the same error code, and counts gains only for journeys the customer never retried. Double-charge exposure uses the hidden debited flag and is scoring only.
- Incident thresholds are compared on the same data used to set them, so the best variant is optimistic.

## Phase 8 assumptions
- The experiment is simulated. The treatment effect is chosen by us (+3 points on recovery) and is not evidence about a real redesign.
- One observation per customer (first eligible failed journey); customers' other journeys are ignored.
- The duplicate-payment baseline uses the observable detector (about 83 percent precision), so it is a proxy.
- The decision rule is fixed before the simulation runs.

## Phase 8-2 assumptions
- Outcomes are simulated as potential outcomes: each customer's observed result is the control outcome and treated customers who failed are flipped to success with the probability that gives the assumed lift. The lifts (+3 pp recovery, +0.8 pp duplicates) are our assumptions.
- A recovery flip also implies a retry. Abandonment is the complement of recovery. Time to completion is not simulated.
- The inconclusive-on-safety branch is not triggered because the guardrail is powered; no extra rule was added after seeing results.
- The duplicate rate is a detector-based proxy (about 83 percent precision).


