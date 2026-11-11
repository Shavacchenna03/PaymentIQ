DROP VIEW IF EXISTS v_dup_detect CASCADE;
DROP TABLE IF EXISTS decision_table;
DROP TABLE IF EXISTS incident_blocks;

-- Bank and 3-hour blocks with a failure rate far above normal (hindsight rule, not a live alert)
CREATE TABLE incident_blocks AS
SELECT bank_id, attempt_date AS d, (EXTRACT(HOUR FROM initiated_at)::int / 3) AS blk,
       COUNT(*) AS attempts,
       COUNT(*) FILTER (WHERE status = 'FAILED') AS failures,
       (COUNT(*) >= 15 AND wilson_lo(COUNT(*) FILTER (WHERE status = 'FAILED'), COUNT(*)) > 20) AS is_incident
FROM v_attempts_eligible GROUP BY 1, 2, 3;
CREATE INDEX idx_ib ON incident_blocks (bank_id, d, blk);

-- Five-way decision for every failed or pending journey start (w30b)
CREATE TABLE decision_table AS
SELECT f.transaction_id, a.customer_id, f.amount, f.status, f.error_code, f.bank_id, f.initiated_at,
       c.retry_class, jn.any_success, jn.n_attempts,
       COALESCE(ib.is_incident, FALSE) AS in_incident,
       CASE WHEN f.status = 'PENDING' THEN 'Wait for status confirmation'
            WHEN f.error_code IN ('CUS_03','TEC_01','RSK_01') THEN 'Do not retry'
            WHEN c.retry_class = 'Verify status first' THEN 'Wait for status confirmation'
            WHEN c.retry_class = 'Escalate' THEN 'Escalate'
            WHEN c.retry_class = 'Customer action' THEN 'Customer action required'
            WHEN c.retry_class = 'Safe retry' AND COALESCE(ib.is_incident, FALSE) THEN 'Wait for status confirmation'
            WHEN c.retry_class = 'Safe retry' THEN 'Eligible for retry evaluation'
       END AS decision,
       CASE WHEN f.status = 'PENDING' THEN 'pending status'
            WHEN f.error_code IN ('CUS_03','TEC_01','RSK_01') THEN 'do-not-retry code'
            WHEN c.retry_class = 'Verify status first' THEN 'status uncertain'
            WHEN c.retry_class = 'Safe retry' AND COALESCE(ib.is_incident, FALSE) THEN 'bank incident hold'
            ELSE c.retry_class END AS reason
FROM journey_attempts a
JOIN fact_transactions f ON f.transaction_id = a.transaction_id
LEFT JOIN dim_failure_codes c ON c.error_code = f.error_code
JOIN journey_summary jn ON jn.variant = 'w30b'
     AND jn.jkey = a.customer_id || '|' || a.payee_id || '|' || a.amount || '|' || a.s30b
LEFT JOIN incident_blocks ib ON ib.bank_id = f.bank_id AND ib.d = f.initiated_at::date
     AND ib.blk = EXTRACT(HOUR FROM f.initiated_at)::int / 3
WHERE a.n30b = 1 AND f.status IN ('FAILED','PENDING');
CREATE INDEX idx_dt_txn ON decision_table (transaction_id);

-- Duplicate-debit detector on observable data: an attempt settled as SUCCESS at the bank after an
-- earlier attempt in the same w30b journey was not an app success but did settle as SUCCESS
CREATE VIEW v_dup_detect AS
WITH j AS (
  SELECT m.jkey, t.transaction_id, t.initiated_at, t.status, r.final_status
  FROM journey_map m
  JOIN fact_transactions t ON t.transaction_id = m.transaction_id
  JOIN fact_reconciliation r ON r.transaction_id = t.transaction_id
  WHERE m.variant = 'w30b'
), o AS (
  SELECT j.*,
         BOOL_OR(status <> 'SUCCESS' AND final_status = 'SUCCESS')
           OVER (PARTITION BY jkey ORDER BY initiated_at, transaction_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS earlier_settled
  FROM j
)
SELECT transaction_id, jkey FROM o WHERE final_status = 'SUCCESS' AND earlier_settled;
