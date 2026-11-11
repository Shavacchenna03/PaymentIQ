DROP TABLE IF EXISTS customer_features;
DROP VIEW IF EXISTS v_retry_gaps;

-- Gap in seconds from a failed first attempt to the next attempt in the same w30b journey
CREATE VIEW v_retry_gaps AS
SELECT a.transaction_id, a.error_code, a.initiated_at,
       EXTRACT(EPOCH FROM (n.initiated_at - COALESCE(f.completed_at, a.initiated_at))) AS gap_s,
       n.status AS next_status
FROM journey_attempts a
JOIN fact_transactions f ON f.transaction_id = a.transaction_id
JOIN journey_attempts n ON n.customer_id = a.customer_id AND n.payee_id = a.payee_id AND n.amount = a.amount
     AND n.s30b = a.s30b AND n.initiated_at > a.initiated_at
WHERE a.status = 'FAILED'
  AND n.initiated_at = (SELECT MIN(m.initiated_at) FROM journey_attempts m
                        WHERE m.customer_id = a.customer_id AND m.payee_id = a.payee_id AND m.amount = a.amount
                          AND m.s30b = a.s30b AND m.initiated_at > a.initiated_at);

CREATE TABLE customer_features AS
SELECT j.customer_id, c.signup_date, c.city_tier,
       COUNT(*) AS journeys,
       COUNT(*) FILTER (WHERE j.first_status = 'FAILED') AS failed_first,
       COUNT(*) FILTER (WHERE j.first_status = 'FAILED' AND j.n_attempts > 1) AS retried,
       COUNT(*) FILTER (WHERE j.first_status = 'FAILED' AND j.any_success) AS recovered,
       COUNT(*) FILTER (WHERE j.first_status = 'FAILED' AND j.n_attempts > 1 AND j.any_success) AS retried_recovered,
       COALESCE(AVG(j.amount), 0) AS avg_amount,
       COALESCE(SUM(j.amount) FILTER (WHERE j.any_success), 0) AS success_value
FROM journey_summary j JOIN dim_customers c ON c.customer_id = j.customer_id
WHERE j.variant = 'w30b'
GROUP BY j.customer_id, c.signup_date, c.city_tier;
