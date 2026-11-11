DROP TABLE IF EXISTS value_journeys;

CREATE TABLE value_journeys AS
SELECT j.jkey, j.customer_id, j.amount, j.n_attempts, j.first_time, j.first_status, j.first_error, j.any_success,
       c.category, c.retry_class, b.size_tier, cu.city_tier,
       (j.first_status = 'FAILED') AS failed_first,
       (j.first_status = 'FAILED' AND j.first_error NOT IN ('CUS_03','TEC_01','RSK_01')) AS eligible,
       CASE WHEN j.amount < 500 THEN '1: under 500'
            WHEN j.amount < 2000 THEN '2: 500-1999'
            WHEN j.amount < 10000 THEN '3: 2000-9999'
            ELSE '4: 10000 and above' END AS value_band
FROM journey_summary j
JOIN LATERAL (SELECT f.bank_id FROM journey_map m JOIN fact_transactions f ON f.transaction_id = m.transaction_id
              WHERE m.variant = 'w30b' AND m.jkey = j.jkey
              ORDER BY f.initiated_at, f.transaction_id LIMIT 1) fb ON TRUE
JOIN dim_banks b ON b.bank_id = fb.bank_id
JOIN dim_customers cu ON cu.customer_id = j.customer_id
LEFT JOIN dim_failure_codes c ON c.error_code = j.first_error
WHERE j.variant = 'w30b';

CREATE INDEX idx_vj_customer ON value_journeys (customer_id);
ANALYZE value_journeys;
