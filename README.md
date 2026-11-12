# PaymentIQ: Payment Reliability, Root-Cause and Recovery Analytics

A portfolio project simulating a Product Analyst at a fictional Indian UPI fintech (PayFlow). All data is synthetic. Thirteen patterns were declared in advance (Git tag `ground-truth-declared`), so every method is scored against an answer key.

**The story:** payment failures look like one problem in aggregate but are several. The biggest value block (timeouts and uncertain statuses, 194.8 lakh) needs a status-check capability, not smarter retries. The biggest single code (per-transaction limits, 27 percent of unrecovered value from 400 journeys) needs a better customer experience. Raw comparisons pointed at the wrong bank.

## Headline results
| Area | Result |
|---|---|
| Scale | 293,991 attempts, 1.15M events, 40 banks, 7 PSPs, 30,000 customers |
| Incident detection | Change-point search recovered the 3 to 16 Aug PSP incident exactly |
| Root cause | Raw view flagged the wrong bank (OR 1.07); controlled model cleared it (1.02) and found the true outlier (OR 1.44 vs 1.42 planted) |
| Scorecard | 12 of 14 estimates within 2 SE of planted values; 2 misses reported |
| Journeys | Domain-aware rule cut mis-merged journeys 93 percent; 81 percent of unrecovered failures never retried |
| Value | 297.5 lakh unrecovered of 402.5 lakh eligible; revenue case weak (about 7,900 rupees for +5 points at 0.5 percent take rate) |
| Recovery | Rules layer with 0 safety violations; duplicate-debit detector 82.6 percent precision, 84.6 percent recall |
| Experiment (simulated) | 96 percent power for +3 pp; guardrail blocked a bad ship (0.1 percent ship rate) |
| Negative results | Customer segmentation weak (ARI 0.064), scoring model rejected, latency regression biased |

## Start here
- reports/executive_report.md: findings across all six workstreams
- reports/project_summary_onepage.md: one-page summary
- docs/interview_case_studies.md and docs/interview_hard_questions.md: the interview pack

## Stack
Python (pandas, numpy, scipy, statsmodels, scikit-learn), PostgreSQL, SQL (views, CTEs, window functions, percentiles), Git, Jupyter. Power BI pages are designed (docs/powerbi_page*_design.md) and pending build.

## Architecture
generator/ (seeded Python simulation, cleaning, loading and analysis scripts) builds PostgreSQL tables in the public, staging and truth schemas. sql/ holds numbered scripts (schema, views, checks). reports/ holds findings and outputs, notebooks/ holds read-only narrative notebooks, docs/ holds design, assumptions and Q&A.

## Reproduce
See docs/reproduce.md for prerequisites and the full run order.

## Method principles
Metric dictionary before code. Ground truth declared before analysis. Never filter rows by the outcome. Scenarios labelled hypothetical. Negative results reported.

## Status
- [x] Phases 0 to 8 complete (tags phase-2-complete to phase-8-complete)
- [ ] Phase 8B: Power BI build (all five pages; see docs/dashboard_backlog.md)
- [x] Phase 9: portfolio packaging

## Documentation
- docs/metric_dictionary.md, docs/data_design.md, docs/ground_truth.md, docs/assumptions.md
- docs/phase_qa.md: questions and answers for every phase
- docs/phase_log.md and docs/dashboard_backlog.md
- reports/data_quality_log.csv: every data quality issue, the rule applied and the accuracy of the fix

All data is synthetic. Bank and PSP names are fictional.
