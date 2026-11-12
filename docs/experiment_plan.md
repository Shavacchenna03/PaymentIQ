# Experiment Plan: Failure Experience (simulated)

This is a simulated experiment on synthetic customers with an effect size we choose. It demonstrates the method and does not show that the redesign works.

## Hypotheses
- H0: the redesigned experience does not change journey recovery.
- H1: it raises recovery by at least 3 percentage points.
- Guardrail: the duplicate-payment rate does not rise by more than 0.5 points (non-inferiority).

## Design
- Unit: customer, randomised 50/50 and sticky (all journeys use the same variant).
- Population: customers with at least one recovery-eligible failed journey. One observation per customer: the first eligible failed journey.
- Control: generic message. Treatment: contextual message, next action, status visibility.

## Metrics
- Primary: journey recovery rate (any attempt in the journey succeeds).
- Guardrail: duplicate-payment rate (detector-based proxy in this simulation).
- Secondary: abandonment, retry rate, time to successful completion.

## Analysis
Two-proportion z-test, 95 percent confidence interval for the difference, logistic regression with covariates as a robustness check, sample ratio mismatch check (chi-square), A/A check, and a 1,000-repeat power study.

## Decision rule (fixed before the simulation)
- Ship: the lower end of the 95 percent interval for the recovery difference is above 0 AND the upper end of the one-sided 95 percent interval for the duplicate-rate difference is below +0.5 points.
- Do not ship: the recovery interval includes 0 or is negative, OR the duplicate upper bound exceeds +0.5 points.
- Inconclusive on safety: recovery is positive but the guardrail is underpowered. Extend the test; do not ship.

## Stopping
Fixed sample size, analysed once. No peeking.
