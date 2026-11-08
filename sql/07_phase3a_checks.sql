-- CHECK: 01 dim_date
-- EXPECT: 183 rows, first date 2026-04-01, last date 2026-09-30
SELECT COUNT(*) AS n, MIN(date_key) AS first_date, MAX(date_key) AS last_date FROM dim_date;

-- CHECK: 02 eligible view row count
-- EXPECT: 291859 (matches validation check 04)
SELECT COUNT(*) AS eligible_attempts FROM v_attempts_eligible;

-- CHECK: 03 derived first-attempt flag versus truth (answer key, used only to score the 30-minute rule)
-- EXPECT: derived_first about 280000 or a little less; true_first 280000; the confusion counts show how wrong the 30-minute rule is
SELECT COUNT(*) FILTER (WHERE f.is_first_attempt) AS derived_first,
       COUNT(*) FILTER (WHERE a.attempt_number = 1) AS true_first,
       COUNT(*) FILTER (WHERE f.is_first_attempt AND a.attempt_number = 1) AS both_first,
       COUNT(*) FILTER (WHERE f.is_first_attempt AND a.attempt_number > 1) AS derived_first_but_retry,
       COUNT(*) FILTER (WHERE NOT f.is_first_attempt AND a.attempt_number = 1) AS derived_retry_but_first
FROM v_attempts_flagged f
JOIN truth.attempt_truth a ON a.transaction_id = f.transaction_id;

-- CHECK: 04 first-attempt and all-attempt failure rate (eligible attempts)
-- EXPECT: all-attempt about 10.39 pct; first-attempt about 9.0 to 9.4 pct
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS all_attempt_failure_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED' AND is_first_attempt) / NULLIF(COUNT(*) FILTER (WHERE is_first_attempt), 0), 2) AS first_attempt_failure_pct,
       COUNT(*) FILTER (WHERE is_first_attempt) AS first_attempts
FROM v_attempts_eligible;

-- CHECK: 05 P95 latency by population
-- EXPECT: all attempts about 8659 ms; first attempts only about 7700 ms
SELECT 'all attempts' AS population,
       ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)) AS p95_ms
FROM v_attempts_flagged WHERE status IN ('SUCCESS','FAILED')
UNION ALL
SELECT 'first attempts',
       ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms))
FROM v_attempts_flagged WHERE status IN ('SUCCESS','FAILED') AND is_first_attempt;
