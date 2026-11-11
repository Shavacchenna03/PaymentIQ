-- CHECK: 01 corrected retry gaps (derived, no 30-minute cut)
-- EXPECT: median 40 to 50 s; share above 1800 s about 4 to 6 pct; derived count slightly above the true retry count because repeat purchases after a failure are included
SELECT COUNT(*) AS gaps,
       ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY gap_s))::numeric) AS median_s,
       ROUND(100.0 * COUNT(*) FILTER (WHERE gap_s > 1800) / COUNT(*), 2) AS pct_above_1800s
FROM v_retry_gaps_any;

-- CHECK: 02 true retry gaps from the answer key
-- EXPECT: about 13991 gaps; median about 40 to 45 s; share above 1800 s about 4 to 6 pct
SELECT COUNT(*) AS gaps,
       ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (f2.initiated_at - COALESCE(f1.completed_at, f1.initiated_at)))))::numeric) AS median_s,
       ROUND(100.0 * COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (f2.initiated_at - COALESCE(f1.completed_at, f1.initiated_at))) > 1800) / COUNT(*), 2) AS pct_above_1800s
FROM truth.attempt_truth t1
JOIN truth.attempt_truth t2 ON t2.intent_id = t1.intent_id AND t2.attempt_number = t1.attempt_number + 1
JOIN fact_transactions f1 ON f1.transaction_id = t1.transaction_id
JOIN fact_transactions f2 ON f2.transaction_id = t2.transaction_id;

-- CHECK: 03 cohorts
-- EXPECT: Before 2026-04 about 18000 customers (fewer with intents); newer cohorts about 2000 each; first_failure_pct about 8 to 10 everywhere with wide intervals for new cohorts
SELECT * FROM v_cohorts ORDER BY cohort;

-- CHECK: 04 activity of new cohorts by calendar month
-- EXPECT: no activity before the signup month; active_pct highest in the signup month, then lower
SELECT cohort, month, active_customers, active_pct FROM v_cohort_activity ORDER BY cohort, month;
