# W2 Root-Cause Report (synthetic PayFlow data, Apr to Sep 2026)

All effects in this data were planted by us and declared before analysis (tag ground-truth-declared). This report says what the methods recovered, not what was discovered about real banks. Causal models use first attempts only (273,574), derived by a 30-minute rule with about 1.6 percent misclassification.

## 1. What is happening?
First-attempt failure rate is 9.05 percent. Network failures are the largest category (40 percent of failures), then bank-side (26), customer (13), PSP-side (13). The top 8 banks hold 65.7 percent of failures on 69.8 percent of volume, so concentration mostly reflects volume. Small banks hold 8.25 percent of volume and 11.28 percent of failures.

## 2. Why is it happening?
- Network quality: 3G and 2G raise network-failure odds about 3.5 and 4.9 times against WiFi.
- One bank has a real penalty: Zenora, odds ratio 1.44 (95 percent CI 1.30 to 1.60) on bank-side failures. Tarang National looks worse in raw data (odds ratio 1.07) only because 25.9 percent of its attempts are on 3G or 2G; with controls its odds ratio is 1.02. This is Simpson's paradox: the raw comparison pointed at the wrong bank.
- Peak hours (20:00 to 21:59) raise bank-side failure 2.1 times at Small banks, 1.25 times at Medium, about 1.1 times at Large.
- Clearwave had a PSP incident from 3 to 16 Aug (odds ratio 19.7). Outside it Clearwave is normal. A change-point search found the window exactly.
- Kestrel Commercial had three outage days, visible at bank level (z 8 to 12) but not system-wide.
- Device type has no detectable effect (all-failures model within plus or minus 5 percent).
- The Rs 10,000 step is a Small-bank per-transaction limit, not unreliability.

## 3. Who or what is affected?
Customers on slow networks, customers of Zenora, Small-bank customers at peak hours, and everyone during the Clearwave window. 17,866 attempts (6.08 percent) have no issuer response, so their debit status is unknown.

## 4. What should the organisation do?
1. Investigate Zenora's integration with the bank (estimated 1.44 times the bank-side failure odds of its peers).
2. Add capacity or routing alternatives for Small banks at 20:00 to 21:59.
3. Treat timeouts and no-issuer-response failures as verify-status cases, never blind retries (52 percent of failures are in this retry class).
4. Monitor releases with change-point detection and outages with bank-level alerts, since system averages hide both.
5. Report limit failures (LIM_02) separately from reliability failures.
6. Do not act on device type.

## 5. What improvement to expect (hypothetical scenario, not a result)
Bank-side failures are about 5,100 of 24,772 first-attempt failures. If Zenora's penalty were removed, its bank-side failure odds would fall by about 31 percent (1 / 1.44), roughly 200 fewer first-attempt failures over six months, under 1 percent of all failures. Financial sizing is deferred to Phase 6.

## Scorecard
12 of 14 numeric estimates within 2 standard errors of the planted values. Outside: Peak Large (z 2.34) and 2G (z 2.10). Three network estimates lean upward, which suggests a small systematic bias, untested. Device equivalence could not be shown within individual cause models for Web (low power).

## Limits
- Synthetic data with declared effects; real data would be messier.
- First attempts only; retries are excluded from causal models.
- 93 repaired UNK_01 rows were excluded from code-level work.
- The Large-bank peak estimate may be inflated by Kestrel's evening outage; untested.

## Correction (added in Phase 5)
Section 5 said removing Zenora's penalty would prevent roughly 200 first-attempt failures. A closer estimate is about 150: Zenora's bank-side failures are roughly 2 percent of its 23,978 first attempts (about 480), and cutting the odds by 31 percent removes about 150. The conclusion is unchanged: under 1 percent of all failures. The original text is left as written.

