-- CHECK: 01 table size
-- EXPECT: 280336 journeys; failed_first 25805; eligible 24610 (same as Phase 5-1)
SELECT COUNT(*) AS journeys, COUNT(*) FILTER (WHERE failed_first) AS failed_first, COUNT(*) FILTER (WHERE eligible) AS eligible FROM value_journeys;

-- CHECK: 02 value summary in lakh rupees (100000 rupees)
-- EXPECT: total about 3500 to 3800 lakh; failed_first about 8 to 11 pct of it; unrecovered about 60 to 70 pct of eligible value; recovery_value_pct a little below the 32.41 count-based figure
SELECT ROUND(SUM(amount) / 100000.0, 1) AS total_lakh,
       ROUND(SUM(amount) FILTER (WHERE failed_first) / 100000.0, 1) AS failed_first_lakh,
       ROUND(SUM(amount) FILTER (WHERE eligible) / 100000.0, 1) AS eligible_lakh,
       ROUND(SUM(amount) FILTER (WHERE eligible AND any_success) / 100000.0, 1) AS recovered_lakh,
       ROUND(SUM(amount) FILTER (WHERE eligible AND NOT any_success) / 100000.0, 1) AS unrecovered_lakh,
       ROUND(100.0 * SUM(amount) FILTER (WHERE eligible AND any_success) / SUM(amount) FILTER (WHERE eligible), 2) AS recovery_value_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE eligible AND any_success) / COUNT(*) FILTER (WHERE eligible), 2) AS recovery_count_pct
FROM value_journeys;

-- CHECK: 03 attempt-level failed value (all eligible failed attempts, including retries)
-- EXPECT: about 30313 failed attempts; value larger than the failed-first journey value because retries that fail are counted again
SELECT COUNT(*) AS failed_attempts, ROUND(SUM(amount) / 100000.0, 1) AS failed_attempt_lakh
FROM v_attempts_eligible WHERE status = 'FAILED';

-- CHECK: 04 by retry class of the first error
-- EXPECT: Verify status first largest by value; Safe retry recovers best; Customer action has the lowest recovery by value
SELECT retry_class, COUNT(*) AS journeys, ROUND(SUM(amount) / 100000.0, 1) AS eligible_lakh,
       ROUND(SUM(amount) FILTER (WHERE NOT any_success) / 100000.0, 1) AS unrecovered_lakh,
       ROUND(100.0 * SUM(amount) FILTER (WHERE any_success) / SUM(amount), 1) AS recovery_value_pct,
       ROUND(AVG(amount)) AS avg_amount
FROM value_journeys WHERE eligible GROUP BY retry_class ORDER BY unrecovered_lakh DESC;

-- CHECK: 05 by category and top codes (unrecovered value)
-- EXPECT: Network and Bank-side hold the most unrecovered value; BNK_03 and LIM_02 show low recovery
SELECT first_error, MAX(category) AS category, COUNT(*) AS journeys,
       ROUND(SUM(amount) FILTER (WHERE NOT any_success) / 100000.0, 1) AS unrecovered_lakh,
       ROUND(100.0 * SUM(amount) FILTER (WHERE any_success) / SUM(amount), 1) AS recovery_value_pct,
       ROUND(AVG(amount)) AS avg_amount
FROM value_journeys WHERE eligible GROUP BY first_error ORDER BY unrecovered_lakh DESC LIMIT 12;

-- CHECK: 06 by bank tier and city tier
-- EXPECT: Large banks hold most unrecovered value; Small banks carry a high unrecovered share per rupee because of the 10000 limit
SELECT 'bank tier' AS dim, size_tier AS grp, COUNT(*) AS journeys,
       ROUND(SUM(amount) FILTER (WHERE NOT any_success) / 100000.0, 1) AS unrecovered_lakh,
       ROUND(100.0 * SUM(amount) FILTER (WHERE any_success) / SUM(amount), 1) AS recovery_value_pct
FROM value_journeys WHERE eligible GROUP BY size_tier
UNION ALL
SELECT 'city tier', city_tier, COUNT(*),
       ROUND(SUM(amount) FILTER (WHERE NOT any_success) / 100000.0, 1),
       ROUND(100.0 * SUM(amount) FILTER (WHERE any_success) / SUM(amount), 1)
FROM value_journeys WHERE eligible GROUP BY city_tier ORDER BY 1, 2;

-- CHECK: 07 by value band
-- EXPECT: most journeys are under 2000; the 10000 and above band has a very low recovery value share (limit failures)
SELECT value_band, COUNT(*) AS journeys, ROUND(SUM(amount) / 100000.0, 1) AS eligible_lakh,
       ROUND(SUM(amount) FILTER (WHERE NOT any_success) / 100000.0, 1) AS unrecovered_lakh,
       ROUND(100.0 * SUM(amount) FILTER (WHERE any_success) / SUM(amount), 1) AS recovery_value_pct
FROM value_journeys WHERE eligible GROUP BY value_band ORDER BY value_band;

-- CHECK: 08 customer concentration of unrecovered value (customers with at least one unrecovered journey, by decile)
-- EXPECT: top decile holds about 25 to 40 pct of unrecovered value; shares fall steadily
WITH c AS (
  SELECT customer_id, SUM(amount) AS unrec FROM value_journeys WHERE eligible AND NOT any_success GROUP BY customer_id
), r AS (SELECT unrec, NTILE(10) OVER (ORDER BY unrec DESC) AS decile FROM c)
SELECT decile, COUNT(*) AS customers, ROUND(100.0 * SUM(unrec) / SUM(SUM(unrec)) OVER (), 1) AS share_of_unrecovered_pct
FROM r GROUP BY decile ORDER BY decile;

-- CHECK: 09 scoring against the hidden intents (answer key), lakh rupees
-- EXPECT: derived eligible, recovered and unrecovered values within about 3 pct of the truth row
WITH t AS (
  SELECT i.first_status, i.final_outcome, f.error_code, f.amount
  FROM truth.intent_truth i
  JOIN truth.attempt_truth a ON a.intent_id = i.intent_id AND a.attempt_number = 1
  JOIN fact_transactions f ON f.transaction_id = a.transaction_id
)
SELECT 'truth' AS src,
       ROUND(SUM(amount) FILTER (WHERE first_status = 'FAILED' AND error_code NOT IN ('CUS_03','TEC_01','RSK_01')) / 100000.0, 1) AS eligible_lakh,
       ROUND(SUM(amount) FILTER (WHERE first_status = 'FAILED' AND error_code NOT IN ('CUS_03','TEC_01','RSK_01') AND final_outcome = 'SUCCESS') / 100000.0, 1) AS recovered_lakh,
       ROUND(SUM(amount) FILTER (WHERE first_status = 'FAILED' AND error_code NOT IN ('CUS_03','TEC_01','RSK_01') AND final_outcome <> 'SUCCESS') / 100000.0, 1) AS unrecovered_lakh
FROM t
UNION ALL
SELECT 'derived w30b',
       ROUND(SUM(amount) FILTER (WHERE eligible) / 100000.0, 1),
       ROUND(SUM(amount) FILTER (WHERE eligible AND any_success) / 100000.0, 1),
       ROUND(SUM(amount) FILTER (WHERE eligible AND NOT any_success) / 100000.0, 1)
FROM value_journeys;

-- CHECK: 10 reconciliation exposure (attempt status differs from bank settlement), observable columns only
-- EXPECT: FAILED to SUCCESS about 530 rows (debited timeouts plus random); PENDING to SUCCESS 482; PENDING to FAILED 702; SUCCESS to FAILED 258
SELECT t.status AS app_status, r.final_status AS bank_status, COUNT(*) AS attempts, ROUND(SUM(t.amount) / 100000.0, 2) AS lakh
FROM fact_transactions t JOIN fact_reconciliation r ON r.transaction_id = t.transaction_id
WHERE t.status <> r.final_status GROUP BY 1, 2 ORDER BY 1, 2;
