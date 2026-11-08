-- CHECK: 01 row counts
-- EXPECT: dim_banks 40, dim_customers 30000, dim_failure_codes 28, dim_psp 7, fact_payment_events 1152396, fact_reconciliation 293991, fact_transactions 293991, staging.stg_transactions 294285, truth.attempt_truth 293991, truth.customer_truth 30000, truth.dq_truth 972, truth.intent_truth 280000, truth.recon_truth 293991, truth.transaction_truth 293991
SELECT 'dim_banks' AS tbl, COUNT(*) AS n FROM dim_banks
UNION ALL SELECT 'dim_customers', COUNT(*) FROM dim_customers
UNION ALL SELECT 'dim_failure_codes', COUNT(*) FROM dim_failure_codes
UNION ALL SELECT 'dim_psp', COUNT(*) FROM dim_psp
UNION ALL SELECT 'fact_payment_events', COUNT(*) FROM fact_payment_events
UNION ALL SELECT 'fact_reconciliation', COUNT(*) FROM fact_reconciliation
UNION ALL SELECT 'fact_transactions', COUNT(*) FROM fact_transactions
UNION ALL SELECT 'staging.stg_transactions', COUNT(*) FROM staging.stg_transactions
UNION ALL SELECT 'truth.attempt_truth', COUNT(*) FROM truth.attempt_truth
UNION ALL SELECT 'truth.customer_truth', COUNT(*) FROM truth.customer_truth
UNION ALL SELECT 'truth.dq_truth', COUNT(*) FROM truth.dq_truth
UNION ALL SELECT 'truth.intent_truth', COUNT(*) FROM truth.intent_truth
UNION ALL SELECT 'truth.recon_truth', COUNT(*) FROM truth.recon_truth
UNION ALL SELECT 'truth.transaction_truth', COUNT(*) FROM truth.transaction_truth
ORDER BY 1;

-- CHECK: 02 orphan checks
-- EXPECT: all four values are 0
SELECT
  (SELECT COUNT(*) FROM fact_payment_events e LEFT JOIN fact_transactions t ON t.transaction_id = e.transaction_id WHERE t.transaction_id IS NULL) AS events_without_txn,
  (SELECT COUNT(*) FROM fact_transactions t LEFT JOIN fact_reconciliation r ON r.transaction_id = t.transaction_id WHERE r.transaction_id IS NULL) AS txn_without_recon,
  (SELECT COUNT(*) FROM fact_transactions t LEFT JOIN truth.transaction_truth x ON x.transaction_id = t.transaction_id WHERE x.transaction_id IS NULL) AS txn_without_truth,
  (SELECT COUNT(*) FROM fact_transactions t LEFT JOIN fact_payment_events e ON e.transaction_id = t.transaction_id AND e.event_type = 'INITIATED' WHERE e.event_id IS NULL) AS txn_without_initiated_event;

-- CHECK: 03 attempt status mix
-- EXPECT: FAILED 30937 (10.52 pct), PENDING 1508 (0.51 pct), SUCCESS 261546 (88.96 pct)
SELECT status, COUNT(*) AS attempts, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM fact_transactions
GROUP BY status
ORDER BY status;

-- CHECK: 04 headline rates per the metric dictionary (PENDING and CUS_03 excluded)
-- EXPECT: eligible about 291900, success_rate about 89.6 pct, failure_rate about 10.4 pct (between 10.3 and 10.5), and the two must add to 100
WITH e AS (
  SELECT status FROM fact_transactions
  WHERE status IN ('SUCCESS','FAILED') AND error_code IS DISTINCT FROM 'CUS_03'
)
SELECT COUNT(*) AS eligible_attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'SUCCESS') / COUNT(*), 2) AS success_rate_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_rate_pct
FROM e;

-- CHECK: 05 failure rate including CUS_03, and pending share (compare with the generator)
-- EXPECT: failure_rate_incl_cus03_pct 10.58, pending_share_pct 0.51
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED')), 2) AS failure_rate_incl_cus03_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'PENDING') / COUNT(*), 2) AS pending_share_pct
FROM fact_transactions;

-- CHECK: 06 reconciliation rate (non-PENDING attempts only)
-- EXPECT: non_pending_attempts 292483, matching 291695, reconciliation_rate_pct 99.7306
SELECT COUNT(*) AS non_pending_attempts,
       COUNT(*) FILTER (WHERE t.status = r.final_status) AS matching,
       ROUND(100.0 * COUNT(*) FILTER (WHERE t.status = r.final_status) / COUNT(*), 4) AS reconciliation_rate_pct
FROM fact_transactions t
JOIN fact_reconciliation r ON r.transaction_id = t.transaction_id
WHERE t.status IN ('SUCCESS','FAILED');

-- CHECK: 07 latency percentiles in ms (SUCCESS and FAILED attempts)
-- EXPECT: p50 about 1900, p95 about 7700 to 8000, p99 about 30000
SELECT ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms)) AS p50_ms,
       ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)) AS p95_ms,
       ROUND(percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms)) AS p99_ms
FROM fact_transactions
WHERE status IN ('SUCCESS','FAILED');

-- CHECK: 08 attempts and failure rate by month
-- EXPECT: 6 months, attempts rising from about 42000 (April) to about 54000 (September), failure rate falling over time with a bump in August (the Clearwave deploy)
SELECT TO_CHAR(DATE_TRUNC('month', initiated_at), 'YYYY-MM') AS month,
       COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*) FILTER (WHERE status IN ('SUCCESS','FAILED')), 2) AS failure_rate_pct
FROM fact_transactions
GROUP BY 1
ORDER BY 1;

-- CHECK: 09 top 8 banks by failed attempts
-- EXPECT: the 8 Large banks, with combined share of failures about 65 to 70 pct
SELECT b.bank_name, b.size_tier, COUNT(*) AS failures,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_of_all_failures_pct
FROM fact_transactions t
JOIN dim_banks b ON b.bank_id = t.bank_id
WHERE t.status = 'FAILED'
GROUP BY b.bank_name, b.size_tier
ORDER BY failures DESC
LIMIT 8;

-- CHECK: 10 evening share (hours 20-21) by PSP group after the timezone fix
-- EXPECT: both groups about 18.7 pct
SELECT CASE WHEN p.psp_name = 'QuickRail' THEN 'QuickRail' ELSE 'Other PSPs' END AS grp,
       COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE EXTRACT(HOUR FROM t.initiated_at) IN (20, 21)) / COUNT(*), 2) AS pct_hours_20_21
FROM fact_transactions t
JOIN dim_psp p ON p.psp_id = t.psp_id
WHERE t.status <> 'PENDING'
GROUP BY 1
ORDER BY 1;

-- CHECK: 11 settlement lag by PSP group after the timezone fix
-- EXPECT: both groups median about 12 to 13.5 hours and about 93 to 95 pct within 24 hours
SELECT CASE WHEN p.psp_name = 'QuickRail' THEN 'QuickRail' ELSE 'Other PSPs' END AS grp,
       ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (r.settlement_time - t.completed_at)) / 3600))::numeric, 2) AS median_lag_hours,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.settlement_time - t.completed_at <= INTERVAL '24 hours') / COUNT(*), 2) AS pct_within_24h
FROM fact_transactions t
JOIN fact_reconciliation r ON r.transaction_id = t.transaction_id
JOIN dim_psp p ON p.psp_id = t.psp_id
WHERE r.final_status = 'SUCCESS' AND t.status <> 'PENDING'
GROUP BY 1
ORDER BY 1;

-- CHECK: 12 truth table loaded: reconciliation mismatch types
-- EXPECT: NONE 291695, PENDING_RESOLVED_FAILED 702, PENDING_RESOLVED_SUCCESS 482, DEBITED_TIMEOUT 382, PENDING_UNRESOLVED 324, RANDOM_REVERSAL 258, RANDOM_SETTLED_FAILED 148
SELECT mismatch_type, COUNT(*) AS n FROM truth.recon_truth GROUP BY 1 ORDER BY 2 DESC;

-- CHECK: 13 truth table loaded: planted data quality issues
-- EXPECT: DUPLICATE_ROW 294, MISSING_ERROR_CODE 93, MISSING_LATENCY 585
SELECT issue_type, COUNT(*) AS n FROM truth.dq_truth GROUP BY 1 ORDER BY 1;

-- CHECK: 14 truth table loaded: duplicate debits and incidents
-- EXPECT: duplicate_debit_rows 280; incident counts are printed for the record
SELECT COUNT(*) FILTER (WHERE is_duplicate_debit) AS duplicate_debit_rows,
       COUNT(*) FILTER (WHERE incident_id = 'P1_OUTAGE') AS outage_rows,
       COUNT(*) FILTER (WHERE incident_id = 'P7_DEPLOY') AS deploy_rows
FROM truth.transaction_truth;

-- CHECK: 15 truth table loaded: attempts per intent
-- EXPECT: 1 -> 267955, 2 -> 10299, 3 -> 1546, 4 -> 200
SELECT n_attempts, COUNT(*) AS intents FROM truth.intent_truth GROUP BY 1 ORDER BY 1;

-- CHECK: 16 indexes created
-- EXPECT: 9 indexes (7 on public tables, 2 on truth tables)
SELECT schemaname, tablename, indexname FROM pg_indexes WHERE indexname LIKE 'idx_%' ORDER BY schemaname, tablename, indexname;

