# W1 Findings: Payment Performance (synthetic PayFlow data, Apr to Sep 2026)

Headline metric: first-attempt failure rate, 9.05 percent derived (true value 8.98 percent). All-attempt failure rate 10.39 percent. Eligible attempts 291,859.

## 1. Is reliability improving?
Yes, slowly. Adjusting for the August incident, the first-attempt failure rate falls about 1.0 percentage point over six months (odds ratio 0.979 per 30 days, 95 percent CI 0.971 to 0.986). Monthly first-attempt rates: 9.40, 9.29, 8.83, 8.72, 9.70, 8.44 percent. The August rise is an incident, not a trend break.

## 2. Which days and hours are unusual?
- Days: 3 to 16 Aug had a first-attempt failure rate of 10.66 percent against 8.92 percent elsewhere. A change-point search found the window exactly. A rolling z-score flagged only 3 of the 14 days, so it is the wrong tool for a sustained shift.
- Bank outages: Kestrel Commercial's failure rate spiked on 14 May, 22 Jul and 9 Sep (z-scores 8 to 12). System-wide z-scores on those days were only 1.4 to 2.4, so the outages are visible only at bank level.
- Hours: the system-wide rate is nearly flat (about 10.2 percent in daytime, 10.7 percent at 20:00 to 21:59). The effect sits in Small banks, whose bank-side failure rate goes from 3.74 to 7.32 percent at peak. Large banks barely move.

## 3. Is volume growing faster than successful transactions?
No. September against April: eligible attempts x1.271, successful attempts x1.286, successful value x1.314.

## 4. Do some value ranges fail more?
Only above Rs 10,000: about 10.2 percent up to Rs 10,000, then 18.7 and 25.6 percent. This is a Small-bank per-transaction limit, not rising unreliability. Small banks above Rs 10,000 fail 90.3 percent of the time (83.1 percent LIM_02, 503 attempts). Large banks go from 9.76 to 10.60 percent, with overlapping intervals.

## 5. Is latency associated with lower success?
Yes in the raw data, but mostly mechanically. Below 5 seconds the failure rate is flat (5.2 to 5.7 percent). Above 5 seconds it reflects timeouts and slow-by-design codes. A regression that tried to control for this was biased by the way slow failures were removed, so it is not used as evidence. Speeding up the platform would not by itself reduce failures.

## Recommendations for later phases
1. Investigate bank-level reliability, not system averages (Phase 4).
2. Separate policy limits (LIM_02) from reliability failures in every failure report.
3. Monitor releases with a change-point method, and alert at bank level for outages.

## Limits
- Data is synthetic. Patterns were declared in advance (tag ground-truth-declared).
- The first-attempt rule is derived and imperfect (5,171 repeat purchases misread as retries, 679 late retries misread as new attempts).
- Detection results for the August window and trend are from one dataset and one run.
