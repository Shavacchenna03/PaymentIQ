# Phase 3 Design: W1 Payment Performance

## Questions
1. Is payment reliability improving or deteriorating?
2. Which days or hours have unusually high failures?
3. Is volume growing faster than successful transactions?
4. Do certain value ranges fail more?
5. Is latency associated with lower success rates?

## Decisions
- Headline reliability metric: first-attempt failure rate. All-attempt rate is shown beside it. Retries depend on customer behaviour, not only on system performance.
- First attempt is derived in SQL: a row with no earlier attempt by the same customer, payee and amount within the previous 30 minutes. It is scored against truth.attempt_truth in step 3A.
- The 24-hour settlement lag rule excludes nothing (extract date 5 Oct 2026). The dashboard shows a visible check for this.
- Statistical depth is light: trend test, change-point check, confidence intervals on bands. Heavier modelling is in Phase 4.
- Population matters: first-attempt P95 latency differs from all-attempt P95 by about 1 second.

## Build plan
- 3A dim_date and reusable views (v_attempts_eligible, v_attempts_flagged)
- 3B daily, weekly, monthly KPIs with window functions
- 3C hour and weekday heatmap data, anomaly flag on the daily rate
- 3D value bands and latency bands
- 3E Python: trend test, change-point, latency with timeouts separated
- 3F findings note and Power BI Page 1

## Expected findings and traps
- P13 trend: volume up about 35 percent, failure rate down about 1 point. Seasonality hides it in daily data.
- P7 deploy: bump in daily failure rate 3 to 16 Aug and Clearwave latency ramp. Monthly view shows only an unexplained August rise.
- P1 outage: three spikes at Kestrel Commercial. Little effect system-wide, visible at bank level.
- P6 amount: limit and risk failures at high values. Small samples, so use confidence intervals.
- P8 latency: 91 percent failure above 10 seconds, but timeouts are slow by definition. Check non-timeout attempts across latency bands first.
- P2 peak hours: small system-wide effect because Small banks carry 8 percent of volume.
