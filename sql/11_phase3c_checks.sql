-- CHECK: 01 heatmap shape
-- EXPECT: 168 cells (7 weekdays x 24 hours); total eligible attempts 291859
SELECT COUNT(*) AS cells, SUM(eligible_attempts) AS eligible FROM v_heatmap_hour_weekday;

-- CHECK: 02 failure rate by hour of day
-- EXPECT: hours 20 and 21 slightly above the daytime rate; night hours noisy because volume is low
SELECT hour_of_day, SUM(eligible_attempts) AS attempts,
       ROUND(100.0 * SUM(failures) / SUM(eligible_attempts), 2) AS failure_rate_pct
FROM v_heatmap_hour_weekday GROUP BY hour_of_day ORDER BY hour_of_day;

-- CHECK: 03 system anomaly flags
-- EXPECT: several days inside 3 to 16 Aug flagged; about 3 to 5 other days flagged; no flags in the first 28 days
SELECT date_key, first_attempts, first_attempt_failure_pct, ROUND(base_mean, 2) AS base_mean, z_score,
       (date_key BETWEEN DATE '2026-08-03' AND DATE '2026-08-16') AS in_deploy_window
FROM v_anomaly_system WHERE is_anomaly ORDER BY date_key;

-- CHECK: 04 anomaly summary
-- EXPECT: flagged_in_deploy_window 5 to 9 of 14; flagged_elsewhere 3 to 5 of about 140 days with a baseline
SELECT COUNT(*) FILTER (WHERE is_anomaly AND date_key BETWEEN DATE '2026-08-03' AND DATE '2026-08-16') AS flagged_in_deploy_window,
       COUNT(*) FILTER (WHERE is_anomaly AND NOT (date_key BETWEEN DATE '2026-08-03' AND DATE '2026-08-16')) AS flagged_elsewhere,
       COUNT(*) FILTER (WHERE base_days >= 28 AND NOT (date_key BETWEEN DATE '2026-08-03' AND DATE '2026-08-16')) AS days_with_baseline_outside_window,
       COUNT(*) FILTER (WHERE is_anomaly AND base_days < 28) AS flagged_without_baseline
FROM v_anomaly_system;

-- CHECK: 05 Kestrel Commercial outage days (system flag versus bank flag)
-- EXPECT: on 14 May, 22 Jul and 9 Sep the Kestrel failure rate is well above its norm; the system-wide flag is probably false
SELECT k.date_key, k.attempts AS kestrel_attempts, k.failure_pct AS kestrel_failure_pct, k.z_score AS kestrel_z, k.is_anomaly AS kestrel_flag,
       s.z_score AS system_z, s.is_anomaly AS system_flag
FROM v_anomaly_kestrel k
JOIN v_anomaly_system s ON s.date_key = k.date_key
WHERE k.date_key IN (DATE '2026-05-14', DATE '2026-07-22', DATE '2026-09-09')
ORDER BY k.date_key;

-- CHECK: 06 Kestrel anomalies overall
-- EXPECT: the three outage days plus a few false alarms
SELECT date_key, attempts, failure_pct, z_score FROM v_anomaly_kestrel WHERE is_anomaly ORDER BY date_key;

-- CHECK: 07 peak hours by bank size (bank-side codes only), hours 20-21 versus other hours
-- EXPECT: Small about 2 times higher in hours 20-21; Large about 1.1 times; Medium in between
SELECT b.size_tier,
       ROUND(100.0 * COUNT(*) FILTER (WHERE e.status = 'FAILED' AND e.error_code IN ('BNK_01','BNK_02','BNK_04','BNK_06') AND EXTRACT(HOUR FROM e.initiated_at) IN (20, 21))
             / NULLIF(COUNT(*) FILTER (WHERE EXTRACT(HOUR FROM e.initiated_at) IN (20, 21)), 0), 2) AS bank_fail_pct_peak,
       ROUND(100.0 * COUNT(*) FILTER (WHERE e.status = 'FAILED' AND e.error_code IN ('BNK_01','BNK_02','BNK_04','BNK_06') AND EXTRACT(HOUR FROM e.initiated_at) NOT IN (20, 21))
             / NULLIF(COUNT(*) FILTER (WHERE EXTRACT(HOUR FROM e.initiated_at) NOT IN (20, 21)), 0), 2) AS bank_fail_pct_other
FROM v_attempts_eligible e
JOIN dim_banks b ON b.bank_id = e.bank_id
GROUP BY b.size_tier ORDER BY b.size_tier;
