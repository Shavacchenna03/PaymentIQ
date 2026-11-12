# Power BI Page 4: Recovery and Financial Impact

Business question: how much value is lost, how much can be recovered, and what is it worth?
Part 1 (W4) is designed now. Part 2 (W5 recovery decisions) is added after Phase 7.

## Data sources
value_journeys, reports/phase6_pools.csv, reports/phase6_scenarios.csv, v_attempts_eligible, fact_reconciliation, dim_failure_codes.

## Layout (W4 part)
- Cards: total value, failed-first value, recovered value, unrecovered value, recovery rate by value and by count.
- Waterfall: failed-first value to recovered and unrecovered.
- Bar: unrecovered value by first error code, coloured by retry class, limit codes highlighted.
- Bar: recovery by value by bank tier and value band.
- Scenario panel: +2, +5, +10 point and limit scenarios with intervals; title and labels say HYPOTHETICAL.
- Take-rate slicer (0.3, 0.5, 1.0 percent) driving a revenue card, labelled as an assumption.
- Reconciliation panel: the three mismatch amounts.

## Rules
- Value and revenue are never shown on the same axis without a label.
- Scenario visuals always carry the hypothetical label.

## Part 2 (W5 recovery decisions)
Data sources: decision_table, incident_blocks, v_dup_detect, reports/phase7_policies.csv, reports/phase7_incident_variants.csv.
- Cards: journeys by decision, value waiting for status confirmation, duplicate-debit candidates flagged.
- Bar: journeys and value by decision, with observed recovery.
- Table: duplicate-debit candidates with amounts (observable columns only).
- Policy panel: retry everything vs rules only vs rules plus score; title says HYPOTHETICAL.
- Incident panel: flagged bank and 3-hour blocks on the bank daily failure chart.
Rules: truth columns are never shown on the dashboard; scoring results appear only as static report figures.

