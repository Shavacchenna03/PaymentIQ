# PaymentIQ: one-page summary

PaymentIQ is a payment reliability, root-cause and recovery analytics project for a fictional UPI fintech (PayFlow). All data is synthetic; 13 patterns were declared in advance (tag ground-truth-declared) so every method can be scored against an answer key.

## Stack
Python (pandas, numpy, scipy, statsmodels, scikit-learn), PostgreSQL (views, CTEs, window functions, percentiles), Git, Jupyter. Power BI pages are designed and pending build.

## What was built
- Data: 40 banks, 7 PSPs, 28 failure codes, 30,000 customers, 293,991 attempts, 1.15M events, reconciliation; four deliberate data-quality issues cleaned with a scored log (a UTC-writing PSP was found from the data alone).
- W1 performance: KPI views, anomaly flags, change-point detection (found the incident window exactly), trend adjusted for the incident (-1.0 pp).
- W2 root cause: Simpson's paradox resolved with cause-specific logistic regression (true outlier OR 1.44 vs 1.42 planted; wrong bank cleared); device null test; scorecard 12 of 14.
- W3 journeys: journeys derived without an ID; a domain-aware rule cut mis-merged journeys by 93 percent; 81 percent of unrecovered failures never retried.
- W4 financial impact: 3,688 lakh attempted, 297.5 lakh unrecovered; limits hold 27 percent; scenarios with bootstrap intervals; revenue case shown to be weak.
- W5 recovery: five-way rules layer with zero safety-audit violations; duplicate-debit detector (82.6 percent precision, 84.6 percent recall); scoring model built and rejected.
- W6 experimentation: PRD, power analysis, pre-registered decision rule, simulated A/B with 1,000 repeats (96 percent power; guardrail blocked a bad ship).

## What it shows
Aggregates and raw comparisons mislead. The largest value block needs a status-check capability, not smarter retries. Rules beat a model here, and a guardrail should overrule a significant primary metric.

## Honest limits
Synthetic data, assumed effect sizes, first-attempt causal models, a simulated experiment, and four reported negative or weak results (latency regression, segmentation, scoring model, two scorecard misses).
