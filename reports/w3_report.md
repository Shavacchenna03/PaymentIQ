# W3 Customer Journeys Report (synthetic PayFlow data, Apr to Sep 2026)

Journeys are derived, not given: no journey_id exists in the raw data. Rule variants were scored against the hidden intents.

## 1. Journey rules and window sensitivity
- Four rules: 15, 30 and 60 minutes, and w30b (30 minutes, plus a new journey after any success).
- Merged journeys (several true intents in one): w15 2,103, w30 5,171, w60 8,400, w30b 346. Split intents (one intent across journeys): about 550 to 680 for all rules, from late retries.
- w30b is the recommended definition: it cuts merging by 93 percent against w30 using one piece of domain logic (a retry follows a failure).
- Recovery on eligible journeys: truth 33.26 percent; w15 31.69, w30 32.29, w30b 32.41, w60 33.33. w60 looks closest only because merged repeat purchases that succeed offset the late retries it also loses: right for the wrong reason.
- Recovery plus abandonment equals 100 percent for every rule; the pessimistic all-failed-first recovery is 31.73 percent (truth).

## 2. Retry timing and the recovery funnel
- Median wait before a retry is about 41 seconds. About 5 percent of retries come after more than 30 minutes (planted; see checks 01 and 02 in reports/phase5_3_checks_output.txt). The first retry-gap view excluded them by construction and showed 0 percent: corrected here.
- Of 24,610 eligible failed journeys (w30b), 45.45 percent were retried and 32.41 percent recovered. 80.7 percent of unrecovered journeys were never retried.
- Recovery depends on the first error: wrong PIN 58 percent, safe-retry codes 38 to 43 percent, timeouts about 31 percent, insufficient funds 6 percent, limit exceeded 3 percent.

## 3. Segments
- Behavioural segments are real at group level: retry rate by true segment is 0.27 (Abandoning), 0.43 (Reliable), 0.54 (Retry-dependent), and High-value amounts are about 2.5 times larger.
- They are not recoverable at customer level. Rules agree with the hidden labels 46.2 percent of the time (adjusted Rand index 0.064), barely above labelling everyone Reliable (about 45 percent). K-means is worse (0.013). Only High-value (55 percent recall) and Reliable (85 percent) are found.
- Reason: customers have about 7 journeys and about 0.7 failures, so individual failure and retry rates are noise. Segment-level targeting needs more history per customer.

## 4. What to do
1. Prompt customers to retry after safe-retry failures: most unrecovered journeys never retried.
2. Do not push retries for insufficient funds and limit errors: recovery is under 6 percent; show a clear next action instead.
3. Use w30b as the journey definition in dashboards and state its error.
4. Target interventions by failure code (observable), not by inferred customer segment (not recoverable).

## Limits
- Synthetic data; retry behaviour was planted.
- Derived journeys misclassify some attempts (346 merged, about 676 split under w30b).
- Segmentation conclusions apply at this sample size only.

## Cohorts (generated)
| cohort | customers | journeys_per_customer | first_failure_pct (ci_low to ci_high) | retry_rate_pct | recovery_all_pct |
|---|---|---|---|---|---|
| 2026-04 | 1933 | 10.88 | 9.32 (8.93 to 9.72) | 42.63 | 31.21 |
| 2026-05 | 2011 | 8.67 | 9.12 (8.70 to 9.56) | 43.84 | 31.32 |
| 2026-06 | 1888 | 6.81 | 9.12 (8.63 to 9.63) | 43.17 | 31.23 |
| 2026-07 | 1908 | 4.95 | 9.18 (8.61 to 9.78) | 42.73 | 31.64 |
| 2026-08 | 1728 | 3.36 | 8.76 (8.06 to 9.52) | 41.65 | 29.47 |
| 2026-09 | 958 | 1.91 | 7.88 (6.73 to 9.21) | 39.58 | 22.92 |
| Before 2026-04 | 17896 | 11.84 | 9.23 (9.11 to 9.35) | 43.85 | 31.03 |

First-attempt failure rate ranges from 7.88% (2026-09) to 9.32% (2026-04), and every cohort's 95% Wilson confidence interval overlaps the pooled rate of 9.21%.
