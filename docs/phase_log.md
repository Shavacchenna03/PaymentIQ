# Phase Log


## Phase 0: Setup (done)
Scaffold, virtual environment, PostgreSQL connection check, GitHub connected.

## Phase 1: Business foundation (done)
Transaction lifecycle, failure taxonomy (16 codes, 5 retry classes), final metric dictionary v1.0, phase Q&A doc.
Key decisions: 30-minute journey window (to be tested), PENDING excluded from rates, CUS_03 excluded, matching denominators for recovery and abandonment.

## Phase 2 design (done)
Data model, 13 planted patterns (ground truth) and generator plan approved.
Decisions: fictional names, 1 Apr to 30 Sep 2026, about 300k attempts with about 20k retries, ground truth committed before Phase 3, no journey_id in raw data.

## Phase 2: Data engineering (done)
Built the PayFlow synthetic ecosystem: 40 fictional banks, 7 PSPs, 28 failure codes, 30,000 customers, 280,000 payment intents, 293,991 attempts (13,991 retries), 1,152,396 events and a reconciliation record for every attempt. Planted 13 patterns in advance (docs/ground_truth.md, Git tag ground-truth-declared), added four data quality issues, and cleaned them with a logged, scored process (reports/data_quality_log.csv). The cleaning found the UTC-writing PSP from the data alone.
Key decisions: no journey_id in the raw data; duplicate-debit rate inflated to 3 percent for statistical power; retries about 14,000 not 20,000; outage moved to a Large bank; latency recovery is approximate (97 percent within 0.5 s).
Database: 10 base tables plus 4 truth tables, validated in SQL. Git tag: phase-2-complete.

## Phase 3 design and 3A (done)
Phase 3 (W1 payment performance) designed: headline metric is the first-attempt failure rate, derived in SQL and scored against the answer key. Built dim_date (183 days) and the views v_attempts_flagged and v_attempts_eligible, which apply the metric dictionary rules in one place. Design in docs/phase3_design.md.


## Phase 3B (done)
Built v_daily_kpis, v_weekly_kpis and v_monthly_kpis with 7-day rolling rates and period-over-period changes. Scored the derived first-attempt failure rate against the answer key. Corrected the repeat-window figure from 75 to 62.5 percent.


## Phase 3C (done)
Built the hour-by-weekday heatmap view and rolling z-score anomaly flags (28-day baseline, z above 2) for the system-wide first-attempt failure rate and for Kestrel Commercial. Results in reports/phase3c_checks_output.txt.