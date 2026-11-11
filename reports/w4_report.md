# W4 Financial Impact Report (synthetic PayFlow data, Apr to Sep 2026)

All figures are from synthetic data. Scenarios are hypothetical, and take rates are assumptions. Values are in lakh rupees (1 lakh = 100,000). Unit is the derived w30b journey, which misstates value slightly (recovered value is 2.9 percent below the hidden-intent truth).

## 1. What is happening?
- Total attempted value: 3,688 lakh (about 36.9 crore).
- Failed first attempts: 419.9 lakh (11.4 percent of value). Recovery-eligible failed journeys: 402.5 lakh.
- Of eligible value, 105.0 lakh recovered and 297.5 lakh unrecovered (95 percent bootstrap interval 285 to 310). Recovery by value is 26.1 percent against 32.4 percent by count, because the largest payments fail most often on limits.
- A failed payment is not lost revenue: about a third of eligible journeys recover.

## 2. Why is it happening?
- LIM_02 (per-transaction limit at Small banks) holds 71.8 lakh unrecovered from 372 journeys (average 19,874 rupees, recovery 2.9 percent). With LIM_03, limits are 81.1 lakh (27 percent of unrecovered value) from 400 journeys.
- Timeouts (NET_01, NET_02, NET_03) hold 98.4 lakh across about 10,400 journeys, recovering about 29 percent.
- Insufficient funds (BNK_03) holds 17.6 lakh and recovers 3.5 percent.
- The 10,000 rupee and above band recovers 15.1 percent by value against about 33 percent below it.

## 3. Who or what is affected?
- Small banks recover 12.4 percent of value against 31.0 percent at Large banks.
- The top 10 percent of customers with unrecovered value hold 60.6 percent of it, largely high-value payments that hit limits.
- City tiers differ little (24.9 to 26.7 percent recovery by value).
- Reconciliation exposure is separate finance work: 7.14 lakh debited but shown as failed, 7.16 lakh pending that settled, 3.65 lakh reversed, about 18 lakh in total.

## 4. What should the organisation do?
1. Fix the limit experience first: explain the limit and offer an alternative rail or split payment. 400 journeys hold as much recoverable value as a 5 point retry gain across 23,692 journeys.
2. For timeouts, check status before any retry; they carry the largest value in the verify-status class and a duplicate debit risk.
3. Nudge retries after safe-retry failures: most unrecovered journeys were never retried (Phase 5).
4. Do not push retries for insufficient funds; show a top-up prompt instead.
5. Have finance work the reconciliation gaps (about 18 lakh).

## 5. What improvement to expect (hypothetical scenarios, not results)
| Scenario | Gain (lakh) | 95 percent interval | Revenue at 0.5 percent |
|---|---|---|---|
| +2 pp retry recovery | 6.3 | 6.1 to 6.5 | 3,144 rupees |
| +5 pp retry recovery | 15.7 | 15.2 to 16.3 | 7,859 rupees |
| +10 pp retry recovery | 31.4 | 30.4 to 32.6 | 15,717 rupees |
| 10 percent of limit value | 8.1 | 7.1 to 9.1 | 4,054 rupees |
| 25 percent of limit value | 20.3 | 17.8 to 22.8 | 10,135 rupees |

Revenue uses assumed take rates of 0.3, 0.5 and 1.0 percent; at 1.0 percent, +5 points is about 15,700 rupees. Intervals reflect sampling noise only, not whether the assumed gains are achievable. That needs an experiment (Phase 8).

## Recommendation
The revenue case is weak: even +10 points is about 15,700 rupees over six months at the base take rate. Prioritise the limit fix and retry nudges on customer-experience and reliability grounds, and treat revenue as a secondary benefit.

## Limits
- Synthetic data; gains and take rates are assumptions.
- A gain assumes extra recoveries look like the average unrecovered journey.
- Derived journeys misstate value slightly (346 merged, about 676 split).
- Journeys started late in September have little time to recover (censoring).
