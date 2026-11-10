-- CHECK: 01 repaired codes
-- EXPECT: repaired_ids 93; unk01_in_fact_transactions is 93 plus the genuine UNK_01 failures (a few hundred in total)
SELECT (SELECT COUNT(*) FROM v_repaired_codes) AS repaired_ids,
       (SELECT COUNT(*) FROM fact_transactions WHERE error_code = 'UNK_01') AS unk01_in_fact_transactions;

-- CHECK: 02 all failed attempts by category
-- EXPECT: total 30937, shares add to 100; Network largest at about 40 to 47 pct, then Bank-side, Customer, PSP-side
SELECT c.category, COUNT(*) AS failures,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM fact_transactions t
JOIN dim_failure_codes c ON c.error_code = t.error_code
WHERE t.status = 'FAILED'
GROUP BY c.category ORDER BY failures DESC;

-- CHECK: 03 all failed attempts by code with cumulative share (Pareto of codes)
-- EXPECT: NET_01 first at about 23 pct; the first 8 codes cover about 75 to 80 pct
SELECT t.error_code, c.category, c.retry_class, COUNT(*) AS failures,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct,
       ROUND(100.0 * SUM(COUNT(*)) OVER (ORDER BY COUNT(*) DESC, t.error_code) / SUM(COUNT(*)) OVER (), 2) AS cumulative_pct
FROM fact_transactions t
JOIN dim_failure_codes c ON c.error_code = t.error_code
WHERE t.status = 'FAILED'
GROUP BY t.error_code, c.category, c.retry_class
ORDER BY failures DESC, t.error_code;

-- CHECK: 04 analysis population
-- EXPECT: eligible_failures 30313; repaired 93; coded_failures 30220 (CUS_03 is already outside the eligible set)
SELECT (SELECT COUNT(*) FROM v_attempts_eligible WHERE status = 'FAILED') AS eligible_failures,
       (SELECT COUNT(*) FROM v_attempts_rc WHERE is_repaired_code) AS repaired,
       (SELECT COUNT(*) FROM v_failures_coded) AS coded_failures;

-- CHECK: 05 coded failures by retry class
-- EXPECT: Verify status first largest at about 50 to 58 pct; Safe retry about 20 to 25; Customer action about 15 to 20; Do not retry and Escalate small
SELECT retry_class, COUNT(*) AS failures,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM v_failures_coded GROUP BY retry_class ORDER BY failures DESC;

-- CHECK: 06 technical failure rate versus headline failure rate (metric dictionary, BNK_03 and BNK_05 excluded)
-- EXPECT: headline 10.39 pct; technical about 7.5 to 8.5 pct (repaired rows sit in Unknown, so they are outside it)
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE e.status = 'FAILED') / COUNT(*), 2) AS headline_failure_rate_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE c.category IN ('Bank-side','PSP-side','Network','Technical')
                                      AND e.error_code NOT IN ('BNK_03','BNK_05')) / COUNT(*), 2) AS technical_failure_rate_pct
FROM v_attempts_eligible e
LEFT JOIN dim_failure_codes c ON c.error_code = e.error_code;

-- CHECK: 07 category mix, first attempts versus retries
-- EXPECT: shares differ modestly; retries repeat the previous code 70 pct of the time, so Network stays large in both
SELECT category,
       COUNT(*) FILTER (WHERE is_first_attempt) AS first_failures,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_first_attempt) / SUM(COUNT(*) FILTER (WHERE is_first_attempt)) OVER (), 2) AS first_share_pct,
       COUNT(*) FILTER (WHERE NOT is_first_attempt) AS retry_failures,
       ROUND(100.0 * COUNT(*) FILTER (WHERE NOT is_first_attempt) / SUM(COUNT(*) FILTER (WHERE NOT is_first_attempt)) OVER (), 2) AS retry_share_pct
FROM v_failures_coded GROUP BY category ORDER BY first_failures DESC;
