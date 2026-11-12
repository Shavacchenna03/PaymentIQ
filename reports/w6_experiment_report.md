# W6 Experimentation Report (simulated, synthetic PayFlow data)

This is a simulated experiment. The treatment effects (+3 pp recovery, +0.8 pp duplicates) are our assumptions. The results show how the method behaves, not whether the redesign works.

## 1. What is the question?
Does the redesigned failure experience (specific message, next action, status visibility) raise journey recovery without raising duplicate payments? See docs/prd_failure_experience.md and docs/experiment_plan.md. The decision rule was fixed before the simulation.

## 2. Design and power
- Unit: customer, 50/50 sticky; one observation per customer (first recovery-eligible failed journey). Population 14,250 (7,125 per arm).
- Baseline recovery 32.41 percent. Duplicate baseline 0.568 percent (detector-based proxy, about 83 percent precise).
- Smallest detectable lift at 80 percent power: 2.22 pp. +3 pp needs 3,906 per arm; +2 pp needs 8,728, so it is not detectable here.
- Guardrail (non-inferiority, +0.5 pp margin) needs 2,796 per arm; the sample supports a margin down to 0.313 pp, so it is powered.

## 3. Results over 1,000 simulated repeats per scenario
| Scenario | Ship rate | Recovery significant | Guardrail pass | Mean recovery diff |
|---|---|---|---|---|
| A: +3 pp recovery, no duplicate change | 96.1% | 96.9% | 99.1% | +3.02 pp (1.50 to 4.55) |
| B: null (A/A) | 2.3% | 2.3% | 98.8% | 0.00 pp (-1.50 to 1.48) |
| C: +3 pp recovery, +0.8 pp duplicates | 0.1% | 96.9% | 0.1% | +3.01 pp |
- A/A false-positive rate (two-sided p below 0.05) was 4.6 percent, close to the nominal 5 percent, so the pipeline is not biased.
- Sample ratio mismatch: flagged 0.0 to 0.2 percent at 50/50, and 100 percent when assignment was 55/45.
- Scenario C shows the guardrail overruling a significant primary metric.

## 4. What one run can and cannot tell you
In a single run (seed 88) the true +3 pp lift appeared as +1.93 pp (95 percent CI 0.37 to 3.48), in the lower tail of the 1.50 to 4.55 range seen across repeats. The null run showed -1.34 pp (p = 0.088). One real experiment is one noisy draw, so a decision should rest on the interval and the pre-registered rule, not on the point estimate. A recovery lift implies more retries by construction in this simulation, so retry is not an independent finding.

## 5. Decision
Under the pre-registered rule: A ships, B does not, C does not. The inconclusive-on-safety branch did not trigger because the guardrail is powered. For a real redesign, we would run the test only if the expected lift is plausibly 2.5 pp or more, because smaller effects need more than 7,125 customers per arm.

## What a real test would need
- A real duplicate-payment measure (reconciliation-confirmed, not a proxy).
- Per-failure-type analysis, since the pooled effect may hide differences between wrong-PIN, timeout and limit cases.
- Time-to-completion logged for every attempt.
- A longer window for late retries and slow settlements.

## Limits
- Effects are assumed; this is a method demonstration.
- One observation per customer ignores other journeys.
- Time to completion was not simulated.
- The duplicate baseline is a proxy.
