# Phase 4 Design: W2 Root Cause

## Questions
1. Which banks contribute disproportionately to failures?
2. Which error codes account for the largest share?
3. Are certain banks unreliable at peak hours?
4. Do high-value transactions fail differently?
5. Are timeouts more common on particular networks?
6. Are failures concentrated around specific PSPs?
Key test: does a bank's difference survive after controlling for volume, time, amount and network?

## Decisions
- Cause-specific models: the outcome is "failed with a code from one cause family" and the denominator is ALL eligible attempts. No rows are filtered by outcome (lesson from the 3E latency regression). An all-failures model is shown beside them.
- Bank effects are fixed effects (40 banks, reference group chosen in 4D), not random effects, so Tarang National and Zenora can be read and scored directly.
- Analysis scripts are .py files with saved results. One narrative notebook is written at 4F.
- The 93 repaired UNK_01 rows are identified from staging.stg_transactions (FAILED with null error_code) and excluded from code-level work.
- Kestrel Commercial outage days are identified from the 3C anomaly flags, not from config, and handled with a dummy or exclusion.
- Scoring: estimates are compared with the planted values in data/raw/failure_truth.csv at 4F.

## Build plan
- 4A failure taxonomy applied (category, code, retry class), repaired rows excluded
- 4B Pareto and concentration, excess failures against volume share
- 4C bank by hour, bank by network, PSP breakdowns
- 4D Simpson's trap: raw rates against logistic regression with controls, bank by peak interaction
- 4E network, device (null effect), PSP and Clearwave deploy effects
- 4F event funnel, RCA report, scoring against the answer key, Page 2 design

## Expected findings
- Pareto: the 8 Large banks produce about 66 percent of failures on 70 percent of volume. Small banks over-contribute. Concentration mostly reflects volume.
- All-failures model: Tarang about 1.0 once network is controlled, Zenora borderline because its effect is diluted.
- Bank-side model: Zenora odds ratio about 1.4, Tarang about 1.0.
- Peak: Small banks about 2 times, Large about 1.1 times.
- Device: odds ratios near 1 (null effect). Network: NET failures about 3.5 times higher on 3G and 2G.
