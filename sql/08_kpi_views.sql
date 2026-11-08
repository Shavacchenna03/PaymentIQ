DROP VIEW IF EXISTS v_monthly_kpis CASCADE;
DROP VIEW IF EXISTS v_weekly_kpis CASCADE;
DROP VIEW IF EXISTS v_daily_kpis CASCADE;

CREATE VIEW v_daily_kpis AS
WITH base AS (
  SELECT d.date_key, d.iso_weekday, d.weekday_name, d.is_weekend, d.is_month_end_window,
         d.week_start, d.year_month,
         COUNT(e.transaction_id) AS eligible_attempts,
         COUNT(*) FILTER (WHERE e.status = 'SUCCESS') AS successes,
         COUNT(*) FILTER (WHERE e.status = 'FAILED') AS failures,
         COUNT(*) FILTER (WHERE e.is_first_attempt) AS first_attempts,
         COUNT(*) FILTER (WHERE e.is_first_attempt AND e.status = 'FAILED') AS first_failures,
         COALESCE(SUM(e.amount) FILTER (WHERE e.status = 'SUCCESS'), 0) AS success_value
  FROM dim_date d
  LEFT JOIN v_attempts_eligible e ON e.attempt_date = d.date_key
  GROUP BY d.date_key, d.iso_weekday, d.weekday_name, d.is_weekend, d.is_month_end_window, d.week_start, d.year_month
)
SELECT b.*,
       ROUND(100.0 * failures / NULLIF(eligible_attempts, 0), 2) AS failure_rate_pct,
       ROUND(100.0 * first_failures / NULLIF(first_attempts, 0), 2) AS first_attempt_failure_pct,
       ROUND(success_value / NULLIF(successes, 0), 2) AS avg_success_value,
       ROUND(100.0 * SUM(failures) OVER w7 / NULLIF(SUM(eligible_attempts) OVER w7, 0), 2) AS failure_rate_7d_pct,
       ROUND(100.0 * SUM(first_failures) OVER w7 / NULLIF(SUM(first_attempts) OVER w7, 0), 2) AS first_attempt_failure_7d_pct,
       ROUND(AVG(eligible_attempts) OVER w7, 0) AS eligible_7d_avg,
       ROW_NUMBER() OVER (ORDER BY date_key) AS day_n
FROM base b
WINDOW w7 AS (ORDER BY date_key ROWS BETWEEN 6 PRECEDING AND CURRENT ROW);

CREATE VIEW v_weekly_kpis AS
WITH w AS (
  SELECT week_start, COUNT(*) AS days_in_week,
         SUM(eligible_attempts) AS eligible_attempts, SUM(successes) AS successes,
         SUM(failures) AS failures, SUM(first_attempts) AS first_attempts,
         SUM(first_failures) AS first_failures, SUM(success_value) AS success_value
  FROM v_daily_kpis GROUP BY week_start
)
SELECT w.*,
       ROUND(100.0 * failures / eligible_attempts, 2) AS failure_rate_pct,
       ROUND(100.0 * first_failures / first_attempts, 2) AS first_attempt_failure_pct,
       ROUND(100.0 * first_failures / first_attempts
             - LAG(100.0 * first_failures / first_attempts) OVER (ORDER BY week_start), 2) AS wow_first_failure_pp
FROM w;

CREATE VIEW v_monthly_kpis AS
WITH m AS (
  SELECT year_month, COUNT(*) AS days_in_month,
         SUM(eligible_attempts) AS eligible_attempts, SUM(successes) AS successes,
         SUM(failures) AS failures, SUM(first_attempts) AS first_attempts,
         SUM(first_failures) AS first_failures, SUM(success_value) AS success_value
  FROM v_daily_kpis GROUP BY year_month
)
SELECT m.*,
       ROUND(100.0 * failures / eligible_attempts, 2) AS failure_rate_pct,
       ROUND(100.0 * first_failures / first_attempts, 2) AS first_attempt_failure_pct,
       ROUND(success_value / successes, 2) AS avg_success_value,
       ROUND(100.0 * (eligible_attempts - LAG(eligible_attempts) OVER (ORDER BY year_month))
             / LAG(eligible_attempts) OVER (ORDER BY year_month), 2) AS mom_volume_pct,
       ROUND(100.0 * first_failures / first_attempts
             - LAG(100.0 * first_failures / first_attempts) OVER (ORDER BY year_month), 2) AS mom_first_failure_pp
FROM m;

