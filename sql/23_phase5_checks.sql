-- CHECK: 01 attempt table and link to the 3A first-attempt count
-- EXPECT: attempts 293991; sum_n30 275508 (equals the derived first-attempt count from Phase 3A)
SELECT COUNT(*) AS attempts, SUM(n30) AS sum_n30 FROM journey_attempts;

-- CHECK: 02 journeys per variant (true intents: 280000)
-- EXPECT: w15 about 278000 to 279500; w30 275508; w60 about 271500 to 273000; w30b about 279500 to 280500
SELECT variant, COUNT(*) AS journeys, ROUND(AVG(n_attempts), 3) AS avg_attempts, MAX(n_attempts) AS max_attempts
FROM journey_summary GROUP BY variant ORDER BY variant;

-- CHECK: 03 scoring against the hidden intents (answer key)
-- EXPECT: w30 merged about 5200 and split about 680; w15 merged about 2100; w60 merged about 8000 or more; w30b merged below 1000
WITH jm AS (
  SELECT m.variant, m.jkey, t.intent_id
  FROM journey_map m JOIN truth.attempt_truth t ON t.transaction_id = m.transaction_id
), merged AS (
  SELECT variant, COUNT(*) FILTER (WHERE n_int > 1) AS merged_journeys
  FROM (SELECT variant, jkey, COUNT(DISTINCT intent_id) AS n_int FROM jm GROUP BY variant, jkey) q GROUP BY variant
), split AS (
  SELECT variant, COUNT(*) FILTER (WHERE n_j > 1) AS split_intents
  FROM (SELECT variant, intent_id, COUNT(DISTINCT jkey) AS n_j FROM jm GROUP BY variant, intent_id) q GROUP BY variant
)
SELECT merged.variant, merged_journeys, split_intents FROM merged JOIN split USING (variant) ORDER BY variant;

-- CHECK: 04 recovery metrics per variant against the truth (metric dictionary definitions)
-- EXPECT: truth row recovery_pct about 33.3 and recovery_all_pct about 31.7; derived rows within a few points; retry_rate_pct about 44 to 46 in truth
WITH d AS (
  SELECT variant, COUNT(*) AS journeys,
         COUNT(*) FILTER (WHERE first_status = 'SUCCESS') AS first_success,
         COUNT(*) FILTER (WHERE first_status = 'FAILED') AS failed_first,
         COUNT(*) FILTER (WHERE first_status = 'FAILED' AND n_attempts > 1) AS retried,
         COUNT(*) FILTER (WHERE first_status = 'FAILED' AND first_error NOT IN ('CUS_03','TEC_01','RSK_01')) AS eligible,
         COUNT(*) FILTER (WHERE first_status = 'FAILED' AND first_error NOT IN ('CUS_03','TEC_01','RSK_01') AND any_success) AS elig_recovered,
         COUNT(*) FILTER (WHERE first_status = 'FAILED' AND any_success) AS ff_recovered
  FROM journey_summary GROUP BY variant
), t AS (
  SELECT 'truth' AS variant, COUNT(*) AS journeys,
         COUNT(*) FILTER (WHERE i.first_status = 'SUCCESS') AS first_success,
         COUNT(*) FILTER (WHERE i.first_status = 'FAILED') AS failed_first,
         COUNT(*) FILTER (WHERE i.first_status = 'FAILED' AND i.n_attempts > 1) AS retried,
         COUNT(*) FILTER (WHERE i.first_status = 'FAILED' AND f.error_code NOT IN ('CUS_03','TEC_01','RSK_01')) AS eligible,
         COUNT(*) FILTER (WHERE i.first_status = 'FAILED' AND f.error_code NOT IN ('CUS_03','TEC_01','RSK_01') AND i.final_outcome = 'SUCCESS') AS elig_recovered,
         COUNT(*) FILTER (WHERE i.first_status = 'FAILED' AND i.final_outcome = 'SUCCESS') AS ff_recovered
  FROM truth.intent_truth i
  JOIN truth.attempt_truth a ON a.intent_id = i.intent_id AND a.attempt_number = 1
  JOIN fact_transactions f ON f.transaction_id = a.transaction_id
)
SELECT variant, journeys,
       ROUND(100.0 * first_success / journeys, 2) AS first_attempt_success_pct,
       failed_first,
       ROUND(100.0 * retried / failed_first, 2) AS retry_rate_pct,
       eligible,
       ROUND(100.0 * elig_recovered / eligible, 2) AS recovery_pct,
       ROUND(100.0 * (eligible - elig_recovered) / eligible, 2) AS abandonment_pct,
       ROUND(100.0 * ff_recovered / failed_first, 2) AS recovery_all_pct
FROM (SELECT * FROM d UNION ALL SELECT * FROM t) q ORDER BY variant;

-- CHECK: 05 sanity rules from the metric dictionary
-- EXPECT: recovery_plus_abandonment 100 for every variant; recovery_all never above recovery
WITH d AS (
  SELECT variant,
         COUNT(*) FILTER (WHERE first_status = 'FAILED' AND first_error NOT IN ('CUS_03','TEC_01','RSK_01')) AS eligible,
         COUNT(*) FILTER (WHERE first_status = 'FAILED' AND first_error NOT IN ('CUS_03','TEC_01','RSK_01') AND any_success) AS rec,
         COUNT(*) FILTER (WHERE first_status = 'FAILED') AS ff,
         COUNT(*) FILTER (WHERE first_status = 'FAILED' AND any_success) AS ff_rec
  FROM journey_summary GROUP BY variant
)
SELECT variant,
       ROUND(100.0 * rec / eligible + 100.0 * (eligible - rec) / eligible, 2) AS recovery_plus_abandonment,
       (100.0 * ff_rec / ff) <= (100.0 * rec / eligible) AS recovery_all_not_above
FROM d ORDER BY variant;

-- CHECK: 06 recovery by first error code, w30b variant (recovery-eligible journeys, top codes by volume)
-- EXPECT: CUS_01 about 75 to 80 pct; NET_01 about 50 to 60 pct; BNK_03 about 20 pct; LIM_02 about 10 pct
SELECT first_error, COUNT(*) AS journeys,
       ROUND(100.0 * COUNT(*) FILTER (WHERE any_success) / COUNT(*), 1) AS recovery_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE n_attempts > 1) / COUNT(*), 1) AS retried_pct
FROM journey_summary
WHERE variant = 'w30b' AND first_status = 'FAILED' AND first_error NOT IN ('CUS_03','TEC_01','RSK_01')
GROUP BY first_error HAVING COUNT(*) >= 300 ORDER BY journeys DESC;
