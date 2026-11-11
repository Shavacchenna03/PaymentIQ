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


## Phase 3D (done)
Built value-band and latency-band views with Wilson 95 percent intervals. Tested the latency trap: failure rate by latency band with and without timeout failures, and within 4G only. Results in reports/phase3d_checks_output.txt.


## Phase 3E and 3F (done)
Python analysis: data-driven change-point (recovered 3 to 16 Aug exactly), trend adjusted for the incident (minus 1.0 points), latency model (flawed by selection bias, reported as a caution) and value step (Small-bank limit). Wrote reports/w1_findings.md answering the five W1 questions and the Power BI Page 1 design. Power BI build is step 3G.


## Dashboard backlog created
Power BI build deferred to Phase 8B. Page 1 is skipped for now, with its design and data sources recorded in docs/dashboard_backlog.md.


## Phase 4 design (done)
W2 root-cause plan approved: cause-specific models plus an all-failures model, fixed bank effects, scripts then a narrative notebook, scoring against failure_truth.csv. Design in docs/phase4_design.md.


## Phase 4A (done)
Built v_repaired_codes, v_attempts_rc and v_failures_coded. Applied the failure taxonomy by category, code and retry class, with the 93 repaired UNK_01 rows excluded from code-level work. Results in reports/phase4a_checks_output.txt.


## Phase 4B (done)
Built v_bank_conc (all eligible attempts and first attempts): failure share against volume share, excess failures, within-tier rate gap and z-score, with Wilson intervals. Results in reports/phase4b_checks_output.txt.


## Phase 4B and 4C (done)
4B: bank concentration view with within-tier gaps. 4C: first-attempt view v_first_rc with bank group, network group and peak flag; breakdowns by network, peak hour, PSP and device. Results in reports/phase4b_checks_output.txt and reports/phase4c_checks_output.txt.


## Phase 4C and 4D (done)
4C: bank by network, peak, PSP and device breakdowns on first attempts. 4D: logistic models M0, M1, M2 (34 bank effects, Holm) and M3 (peak by tier), scored against planted values. Zenora recovered (OR 1.44 against planted 1.42), Tarang cleared (OR 1.02), peak effects recovered for Small and Medium, Large slightly high (0.109 against 0). Results in reports/phase4d_results.txt.


## Phase 4E (done)
Device null tested (likelihood-ratio and plus or minus 5 percent equivalence), network and PSP effects scored against planted values, and within-tier bank deviations with Holm correction. Zenora is the only bank that differs from its tier, 0 false positives, no device effect detected, Clearwave bad only inside 3 to 16 Aug. 2G effect marginally above the planted value (2.1 SE). Results in reports/phase4e_results.txt.


## Phase 4F-1 (done)
Built v_funnel from the payment events: stop point per attempt, step timing, and breakdowns by failure code, category, bank tier, PSP and network. Results in reports/phase4f1_checks_output.txt.


## Phase 4F-2 (done)
Scorecard of 14 numeric estimates and 7 qualitative checks against planted values, with misses reported. Saved to reports/phase4_scorecard.csv and reports/figures/p4f_scorecard.png.


## Phase 4 (done)
W2 root cause complete: taxonomy, concentration, Simpson's regression, device null, network and PSP effects, funnel, scorecard (12 of 14 hits), RCA report, notebook, Page 2 design. Tag phase-4-complete.


## Phase 5-1 (done)
Derived journeys at 15, 30 and 60 minutes plus the w30b rule, scored merged and split journeys against the hidden intents, and computed recovery, retry and abandonment metrics per variant against the truth. Results in reports/phase5_1_checks_output.txt.


## Phase 5-2 (done)
Retry timing and recovery funnel on w30b journeys, customer features, rule-based and k-means segmentation scored blind against truth.customer_truth. Results in reports/phase5_results.txt.


## Phase 5 (done)
W3 complete: four journey rules scored against hidden intents (w30b best), recovery funnel, corrected retry-gap view, blind segmentation (weak, reported), cohorts, report, notebook, Page 3 design. Tag phase-5-complete.


## Phase 6-1 (done)
Built value_journeys (w30b) and measured failed, recovered and unrecovered value by retry class, code, bank tier, city tier, value band and customer decile, scored against the hidden intents, plus the reconciliation money gap. Results in reports/phase6_1_checks_output.txt.


## Phase 6-2 (done)
Scenario model: retry-addressable pool with +2, +5 and +10 point recovery gains, a separate speculative limit scenario, take-rate sensitivity (0.3, 0.5, 1.0 percent) and bootstrap intervals. All labelled hypothetical. Results in reports/phase6_results.txt.
