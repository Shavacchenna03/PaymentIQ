DROP VIEW IF EXISTS v_anomaly_system CASCADE;
DROP VIEW IF EXISTS v_anomaly_kestrel CASCADE;
DROP VIEW IF EXISTS v_heatmap_hour_weekday CASCADE;

CREATE VIEW v_heatmap_hour_weekday AS
SELECT EXTRACT(ISODOW FROM initiated_at)::int AS iso_weekday,
       EXTRACT(HOUR FROM initiated_at)::int AS hour_of_day,
       COUNT(*) AS eligible_attempts,
       COUNT(*) FILTER (WHERE status = 'FAILED') AS failures,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_rate_pct
FROM v_attempts_eligible
GROUP BY 1, 2;

CREATE VIEW v_anomaly_system AS
WITH s AS (
  SELECT date_key, first_attempts, first_failures, first_attempt_failure_pct,
         AVG(first_attempt_failure_pct) OVER w AS base_mean,
         STDDEV_SAMP(first_attempt_failure_pct) OVER w AS base_sd,
         COUNT(first_attempt_failure_pct) OVER w AS base_days
  FROM v_daily_kpis
  WINDOW w AS (ORDER BY date_key ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)
)
SELECT s.*,
       ROUND((first_attempt_failure_pct - base_mean) / NULLIF(base_sd, 0), 2) AS z_score,
       CASE WHEN base_days >= 28 AND (first_attempt_failure_pct - base_mean) / NULLIF(base_sd, 0) > 2 THEN TRUE ELSE FALSE END AS is_anomaly
FROM s;

CREATE VIEW v_anomaly_kestrel AS
WITH k AS (
  SELECT e.attempt_date AS date_key,
         COUNT(*) AS attempts,
         COUNT(*) FILTER (WHERE e.status = 'FAILED') AS failures,
         100.0 * COUNT(*) FILTER (WHERE e.status = 'FAILED') / COUNT(*) AS failure_pct
  FROM v_attempts_eligible e
  JOIN dim_banks b ON b.bank_id = e.bank_id
  WHERE b.bank_name = 'Kestrel Commercial'
  GROUP BY e.attempt_date
), s AS (
  SELECT k.*,
         AVG(failure_pct) OVER w AS base_mean,
         STDDEV_SAMP(failure_pct) OVER w AS base_sd,
         COUNT(failure_pct) OVER w AS base_days
  FROM k
  WINDOW w AS (ORDER BY date_key ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)
)
SELECT date_key, attempts, failures, ROUND(failure_pct, 2) AS failure_pct,
       ROUND((failure_pct - base_mean) / NULLIF(base_sd, 0), 2) AS z_score,
       CASE WHEN base_days >= 28 AND (failure_pct - base_mean) / NULLIF(base_sd, 0) > 2 THEN TRUE ELSE FALSE END AS is_anomaly
FROM s;
