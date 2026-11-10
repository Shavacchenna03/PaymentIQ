# Power BI Page 1: Executive Overview

Business question: how reliable are PayFlow payments, and is it getting better?

## Data sources (PostgreSQL views)
v_daily_kpis, v_weekly_kpis, v_monthly_kpis, v_heatmap_hour_weekday, v_anomaly_kestrel, dim_date.

## Layout
- KPI cards (top row): first-attempt failure rate, all-attempt failure rate, eligible attempts, average successful value, P95 latency (all attempts and first attempts), pending share.
- Line chart: daily first-attempt failure rate with 7-day rolling line. Mark 3 to 16 Aug.
- Column and line chart: monthly eligible attempts and first-attempt failure rate.
- Heatmap: failure rate by hour and weekday, with attempts as a tooltip. Hide cells under 500 attempts.
- Kestrel Commercial panel: daily failure rate with the three outage days.
- Value-band bar chart with 95 percent intervals, and a note that the Rs 10,000 step is a Small-bank limit.
- Visible data check (small card): "All attempts older than 24 hours at extract: 100 percent. Pending share 0.51 percent."
- Slicers: month, weekday, bank size tier.

## Rules
- Every KPI uses the metric dictionary definition and matches the SQL checks.
- First-attempt metrics are labelled as derived by the 30-minute rule.
- One DAX measure per KPI, named as in docs/metric_dictionary.md.
