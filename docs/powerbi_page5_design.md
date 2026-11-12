# Power BI Page 5: Product Experiments

Business question: should we ship the failure-experience redesign?
Data sources: reports/phase8_power.csv, reports/phase8_sim_repeats.csv, reports/phase8_sim.txt figures. Static simulated data only.

## Layout
- Banner: "SIMULATED EXPERIMENT. Effects are assumptions."
- Cards: population, baseline recovery, smallest detectable lift, guardrail margin supported.
- Sample-size curve and MDE curve.
- Scenario table: ship rate, recovery significant, guardrail pass.
- Interval chart: recovery difference and duplicate upper bound against the margin.
- Decision panel showing the pre-registered rule and each scenario's outcome.

## Rules
- Every visual carries the SIMULATED label.
- Control versus treatment comparisons use the same axis.
