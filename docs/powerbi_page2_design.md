# Power BI Page 2: Failure Intelligence

Business question: where do payments fail, and is it the bank, network, PSP or customer?

## Data sources
v_failures_coded, v_bank_conc, v_first_rc, v_funnel, reports/phase4_scorecard.csv, dim_banks, dim_psp.

## Layout
- Cards: failure rate, technical failure rate, share of failures from top 8 banks, share with no issuer response.
- Pareto: failures by code with cumulative share, coloured by retry class.
- Bank scatter: volume share against failure share, tier colours, Tarang National and Zenora labelled.
- Matrix: bank group by network group failure rate.
- Bar: bank-side failure by tier, peak against other hours.
- Funnel: stop point by failure category.
- PSP chart: daily PSP-side rate with the 3 to 16 Aug window marked.
- Note panel: raw versus adjusted odds for Tarang National and Zenora (from the scorecard).

## Rules
- Banks are compared within tier. Small-bank rankings are not shown without intervals.
- Customer-side and limit codes are shown separately from reliability failures.
