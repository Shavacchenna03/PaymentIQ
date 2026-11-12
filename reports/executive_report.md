# PaymentIQ Executive Report (synthetic PayFlow data, Apr to Sep 2026)

All data is synthetic. Patterns were declared before analysis (Git tag ground-truth-declared), so this report states what the methods recovered, not what was discovered about real banks. Scenarios are hypothetical, take rates are assumptions, and the experiment is simulated. Values are in lakh rupees (1 lakh = 100,000).

Scale: 293,991 payment attempts from 280,000 intents, 30,000 customers, 40 fictional banks, 7 fictional PSPs, 1,152,396 lifecycle events. 291,859 attempts are eligible for rates (PENDING and customer-cancelled excluded).

## 1. What is happening?
- First-attempt failure rate is 9.05 percent (derived; true value 8.98). All-attempt failure rate is 10.39 percent.
- Reliability is improving slowly: about 1.0 percentage point over six months once an incident is adjusted for (odds ratio 0.979 per 30 days, 95 percent CI 0.971 to 0.986). Volume grew faster than failures: September against April, attempts x1.271, successes x1.286, successful value x1.314.
- Total attempted value is 3,688 lakh. Failed first attempts hold 419.9 lakh. Of 402.5 lakh in recovery-eligible failed journeys, 105.0 lakh recovered and 297.5 lakh did not (95 percent bootstrap interval 285 to 310).
- A failed payment is not lost revenue: about a third of eligible failed journeys recover (32.4 percent by count, 26.1 percent by value).

## 2. Why is it happening?
- Network quality is the largest cause (40 percent of failures). 3G and 2G raise network-failure odds about 3.5 and 4.9 times against WiFi.
- One bank has a real penalty. Zenora: odds ratio 1.44 (95 percent CI 1.30 to 1.60) on bank-side failures. The raw view pointed at the wrong bank: Tarang National looked worse (odds ratio 1.07) only because 25.9 percent of its attempts are on 3G or 2G; with controls it is 1.02. This is Simpson's paradox.
- Concentration mostly reflects volume: the top 8 banks hold 65.7 percent of failures on 69.8 percent of volume. Small banks hold 8.25 percent of volume and 11.28 percent of failures.
- Peak hours (20:00 to 21:59) raise bank-side failure about 2.1 times at Small banks, 1.25 times at Medium, 1.1 times at Large. The system-wide hourly rate is nearly flat, so the effect is invisible in aggregates.
- Incidents: Clearwave (PSP) was bad from 3 to 16 Aug (a change-point search found the window exactly: 10.66 percent against 8.92 percent). Kestrel Commercial had three outage days (bank-level z-scores 8 to 12, system-wide only 1.4 to 2.4).
- Policy limits: a Small-bank Rs 10,000 per-transaction limit causes 90.3 percent failure above Rs 10,000 at those banks. It is a policy limit, not unreliability.
- Device type has no detectable effect (within plus or minus 5 percent in the all-failures model).
- Latency is mostly a symptom: timeouts are slow by definition, and below 5 seconds latency says nothing about failure.

## 3. Who or what is affected?
- Customers on slow networks, customers of Zenora, Small-bank customers at peak hours, and everyone during the Clearwave window.
- 17,866 attempts (6.08 percent) have no issuer response, so their debit status is unknown.
- 81 percent of unrecovered failed journeys were never retried. Recovery depends on the first error: wrong PIN 58 percent, safe-retry codes 38 to 43 percent, timeouts about 31 percent, insufficient funds 6 percent, limit exceeded 3 percent.
- Limit failures (400 journeys) hold 81.1 lakh, 27 percent of unrecovered value. Small banks recover 12.4 percent of value against 31.0 percent at Large banks. The top 10 percent of customers hold 60.6 percent of unrecovered value.
- Reconciliation exposure is about 18 lakh: 7.14 debited but shown as failed, 7.16 pending that settled, 3.65 reversed.

## 4. What should the organisation do?
1. Fix the limit experience: explain the limit and offer an alternative option. 400 journeys hold as much recoverable value as a 5 point retry gain across 23,692 journeys.
2. Build a status-check (reconciliation lookup) for timeouts and pending attempts. This unlocks the largest block (194.8 lakh, 14,617 journey starts) safely and is the highest-value next step.
3. Adopt the rules layer: never retry where status is uncertain, never retry do-not-retry codes, hold safe retries during bank incidents (threshold 15 attempts, Wilson lower bound 25 percent). A retry-everything policy would put 916 already-debited journey starts (12.85 lakh) at risk of a second charge.
4. Run the duplicate-debit detector daily (precision 82.6 percent, recall 84.6 percent against hidden truth) and refund confirmed double charges.
5. Investigate Zenora's bank integration and add capacity or routing for Small banks at peak.
6. Monitor releases with change-point detection and outages with bank-level alerts; system averages hide both.
7. Show specific failure messages with a next action, and test them (see below).
8. Do not act on device type. Do not deploy the scoring model.

## 5. What improvement to expect (hypothetical, not results)
- Retry recovery gains of +2, +5, +10 points would recover about 6.3, 15.7 and 31.4 lakh of transaction value. Recovering 10 to 25 percent of limit value would recover 8.1 to 20.3 lakh.
- Revenue is small: at an assumed 0.5 percent take rate (0.3 to 1.0 range), +5 points is about 7,900 rupees over six months. The case for the work is customer experience and reliability, not revenue.
- The redesign experiment is simulated: with 7,125 customers per arm, a true +3 point lift would be detected about 96 percent of the time, the pre-registered guardrail blocks shipping when duplicates rise by 0.8 points (0.1 percent ship rate), and the smallest detectable lift is 2.22 points.

## What did not work (reported, not hidden)
- A latency regression that removed slow failures but kept all successes was biased (it made 2G look safer than WiFi). It is reported as a caution, not a finding.
- Customer segments are not recoverable at customer level: rules agreed with hidden labels 46 percent of the time (adjusted Rand index 0.064), barely above labelling everyone Reliable. K-means was worse. Segment means differ in the planted direction at group level only.
- The scoring model added little over the rules (within-group AUC 0.529, top-decile lift 1.18). Recommended not to ship.
- Scorecard: 12 of 14 estimates within 2 standard errors of planted values. Misses: Large-bank peak effect (z 2.34) and the 2G network effect (z 2.10), plausibly from the Kestrel evening outage and the derived first-attempt flag; both untested explanations.
- Several of my own expected ranges were wrong and were corrected against the data (for example the repeat-purchase window share, 75 versus 62.5 percent).

## Limits
- Synthetic data with declared effects; real data would be messier and effects less clean.
- First attempts only in causal models (derived by a 30-minute rule, about 1.6 percent misclassified). Derived journeys misstate value slightly (recovered value 2.9 percent below truth).
- Duplicate-debit rate was inflated to 3 percent of timeouts for statistical power; real rates would be lower.
- Policy simulation assumes system retries succeed like customer retries; self-selection means true rates are likely lower.
- The incident rule uses same-block hindsight and optimistic thresholds; a live version would detect later.
- Correction: removing Zenora's penalty would prevent about 150 first-attempt failures (not 200), under 1 percent of all failures.
