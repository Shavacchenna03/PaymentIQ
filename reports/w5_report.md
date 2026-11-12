# W5 Recovery Intelligence Report (synthetic PayFlow data, Apr to Sep 2026)

All figures are from synthetic data. Policy results are hypothetical counterfactuals using observed customer retry success rates, not achieved results. This is decision support, not a live payment engine.

## 1. What is happening?
- 27,165 failed or pending journey starts (w30b). Only 5,833 (21 percent, 74.9 lakh) are safe to evaluate for a retry. 14,617 (54 percent, 194.8 lakh) need the status confirmed first, 5,002 need customer action, 1,195 must never be retried, 518 need escalation.
- 916 starts (12.85 lakh) were already debited. 915 of them fall in "Wait for status confirmation".
- Customer action hides two groups: wrong PIN recovers 58.5 percent, insufficient funds 6.0 percent, limit exceeded 3.5 percent.

## 2. Why is it happening?
A timeout or missing status does not prove a failure, so retrying can charge twice. Retries during a bank outage mostly fail (11.4 percent recovery inside incident blocks against 38.9 percent outside).

## 3. The three layers
1. Rules layer: five decisions from retry class, status certainty and an incident hold. A hard-rule audit found 0 violations.
2. Incident hold: a bank and 3-hour block is held when its failure-rate Wilson lower bound exceeds a threshold. The first version (15 attempts, 20 percent) had 94.6 percent recall but 48.1 percent precision (6 false blocks). The (15, 25) variant keeps 94.6 percent recall with 90.3 percent precision and 0 false blocks. Thresholds were compared on the data that set them, so this is optimistic, and the rule uses same-block hindsight, so a live version would detect incidents later.
3. Scoring model: logistic regression, trained April to July, tested August to September. Across all test rows AUC is 0.658 against 0.570 for the rules, but almost all of that comes from the error code, which the rules already use. Within the Eligible group AUC is 0.529 (95 percent CI 0.507 to 0.553) and top-decile lift 1.18 (1.05 to 1.34). Calibration is good. The model did not earn its place.

## 4. Duplicate-debit detection
An observable rule (an attempt that settled at the bank after an earlier attempt in the same journey was not an app success but did settle) was scored against the hidden truth: 287 flagged, 237 true positives, 50 false positives, 43 misses; precision 82.6 percent, recall 84.6 percent. 33 of 43 misses are debits still pending at the bank; 44 of 50 false alarms are merged repeat purchases from the journey rule.

## 5. Policy comparison (hypothetical, test period Aug to Sep)
| Policy | Retries sent | Expected extra recovered (lakh) | Expected double charges |
|---|---|---|---|
| Retry everything | 9,985 | 55.46 | 143.6 (2.27 lakh) |
| Rules only | 2,313 | 10.31 | 0 |
| Rules plus score | 1,157 | 5.23 | 0 |

Retry everything recovers about five times more value but sends 9,985 retries, expects about 2,000 to fail, causes about 144 double charges, and counts recovery on uncertain and customer-action journeys where a system retry is unlikely to work as the customer did.

## What should the organisation do?
1. Adopt the rules layer with the (15, 25) incident hold. Never retry where status is uncertain.
2. Build status-check (reconciliation lookup) for timeouts and pending attempts: this unlocks the largest block (194.8 lakh) safely. This is the highest-value next step.
3. Run the duplicate-debit detector daily and refund confirmed double charges.
4. Do not deploy the scoring model; revisit with richer features.
5. Test system-triggered retries in an experiment (Phase 8) before trusting the simulated recovery.

## Limits
- Synthetic data; retry behaviour was planted.
- Simulated recovery assumes system retries succeed like customer retries; customers who chose to retry are self-selected, so true rates are likely lower.
- The test period includes the Clearwave incident and outage windows.
- Duplicate-debit exposure uses hidden flags and is scoring only.
