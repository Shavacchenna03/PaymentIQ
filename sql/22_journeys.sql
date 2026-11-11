DROP TABLE IF EXISTS journey_summary;
DROP TABLE IF EXISTS journey_map;
DROP TABLE IF EXISTS journey_attempts;

-- One row per attempt with a journey sequence number for each rule variant
CREATE TABLE journey_attempts AS
WITH x AS (
  SELECT transaction_id, customer_id, payee_id, amount, status, error_code, initiated_at,
         LAG(initiated_at) OVER w AS prev_t, LAG(status) OVER w AS prev_status
  FROM fact_transactions
  WINDOW w AS (PARTITION BY customer_id, payee_id, amount ORDER BY initiated_at, transaction_id)
), y AS (
  SELECT *,
         (prev_t IS NULL OR initiated_at - prev_t > INTERVAL '15 minutes')::int AS n15,
         (prev_t IS NULL OR initiated_at - prev_t > INTERVAL '30 minutes')::int AS n30,
         (prev_t IS NULL OR initiated_at - prev_t > INTERVAL '60 minutes')::int AS n60,
         (prev_t IS NULL OR initiated_at - prev_t > INTERVAL '30 minutes' OR prev_status = 'SUCCESS')::int AS n30b
  FROM x
)
SELECT y.*,
       SUM(n15) OVER w2 AS s15, SUM(n30) OVER w2 AS s30, SUM(n60) OVER w2 AS s60, SUM(n30b) OVER w2 AS s30b
FROM y
WINDOW w2 AS (PARTITION BY customer_id, payee_id, amount ORDER BY initiated_at, transaction_id);

CREATE INDEX idx_ja_txn ON journey_attempts (transaction_id);

-- Attempt to journey key, for every variant
CREATE TABLE journey_map AS
SELECT v.variant, a.transaction_id,
       a.customer_id || '|' || a.payee_id || '|' || a.amount || '|' || v.seq AS jkey
FROM journey_attempts a
CROSS JOIN LATERAL (VALUES ('w15', a.s15), ('w30', a.s30), ('w60', a.s60), ('w30b', a.s30b)) AS v(variant, seq);

CREATE INDEX idx_jm_txn ON journey_map (transaction_id);
CREATE INDEX idx_jm_variant_key ON journey_map (variant, jkey);

-- One row per derived journey
CREATE TABLE journey_summary AS
SELECT v.variant,
       a.customer_id || '|' || a.payee_id || '|' || a.amount || '|' || v.seq AS jkey,
       a.customer_id, a.payee_id, a.amount,
       COUNT(*) AS n_attempts,
       MIN(a.initiated_at) AS first_time,
       (ARRAY_AGG(a.status ORDER BY a.initiated_at, a.transaction_id))[1] AS first_status,
       (ARRAY_AGG(a.error_code ORDER BY a.initiated_at, a.transaction_id))[1] AS first_error,
       BOOL_OR(a.status = 'SUCCESS') AS any_success
FROM journey_attempts a
CROSS JOIN LATERAL (VALUES ('w15', a.s15), ('w30', a.s30), ('w60', a.s60), ('w30b', a.s30b)) AS v(variant, seq)
GROUP BY v.variant, a.customer_id, a.payee_id, a.amount, v.seq;

ANALYZE journey_map;
ANALYZE journey_summary;
