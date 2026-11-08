DROP VIEW IF EXISTS v_attempts_eligible CASCADE;
DROP VIEW IF EXISTS v_attempts_flagged CASCADE;

-- Flags each attempt: derived first attempt (no earlier attempt by same customer, payee, amount within 30 minutes)
CREATE VIEW v_attempts_flagged AS
SELECT t.*,
       COALESCE(
         LAG(t.initiated_at) OVER (PARTITION BY t.customer_id, t.payee_id, t.amount ORDER BY t.initiated_at, t.transaction_id)
         < t.initiated_at - INTERVAL '30 minutes',
         TRUE
       ) AS is_first_attempt,
       t.initiated_at::date AS attempt_date
FROM fact_transactions t;

-- Metric dictionary rule: terminal attempts only, customer-cancelled excluded
CREATE VIEW v_attempts_eligible AS
SELECT *
FROM v_attempts_flagged
WHERE status IN ('SUCCESS','FAILED')
  AND error_code IS DISTINCT FROM 'CUS_03';
