DROP VIEW IF EXISTS v_cohort_activity CASCADE;
DROP VIEW IF EXISTS v_cohorts CASCADE;
DROP VIEW IF EXISTS v_retry_gaps_any CASCADE;

-- Gap from a failed attempt to the next attempt of the same customer, payee, amount, up to 180 minutes (no 30-minute cut)
CREATE VIEW v_retry_gaps_any AS
WITH x AS (
  SELECT transaction_id, status, error_code, initiated_at, completed_at,
         LEAD(initiated_at) OVER w AS next_t, LEAD(status) OVER w AS next_status
  FROM fact_transactions
  WINDOW w AS (PARTITION BY customer_id, payee_id, amount ORDER BY initiated_at, transaction_id)
)
SELECT transaction_id, error_code, next_status,
       EXTRACT(EPOCH FROM (next_t - COALESCE(completed_at, initiated_at))) AS gap_s
FROM x
WHERE status = 'FAILED' AND next_t IS NOT NULL AND next_t - initiated_at <= INTERVAL '180 minutes';

CREATE VIEW v_cohorts AS
SELECT CASE WHEN signup_date < DATE '2026-04-01' THEN 'Before 2026-04' ELSE TO_CHAR(signup_date, 'YYYY-MM') END AS cohort,
       COUNT(*) AS customers,
       SUM(journeys) AS journeys,
       ROUND(SUM(journeys)::numeric / COUNT(*), 2) AS journeys_per_customer,
       SUM(failed_first) AS failed_first,
       ROUND(100.0 * SUM(failed_first) / SUM(journeys), 2) AS first_failure_pct,
       wilson_lo(SUM(failed_first), SUM(journeys)) AS ci_low,
       wilson_hi(SUM(failed_first), SUM(journeys)) AS ci_high,
       ROUND(100.0 * SUM(retried) / NULLIF(SUM(failed_first), 0), 2) AS retry_rate_pct,
       ROUND(100.0 * SUM(recovered) / NULLIF(SUM(failed_first), 0), 2) AS recovery_all_pct,
       ROUND(AVG(avg_amount), 0) AS avg_amount
FROM customer_features GROUP BY 1;

-- Share of each signup cohort (all customers in dim_customers) active in each calendar month
CREATE VIEW v_cohort_activity AS
WITH c AS (
  SELECT customer_id, TO_CHAR(signup_date, 'YYYY-MM') AS cohort FROM dim_customers WHERE signup_date >= DATE '2026-04-01'
), a AS (
  SELECT DISTINCT customer_id, TO_CHAR(initiated_at, 'YYYY-MM') AS month FROM fact_transactions
)
SELECT c.cohort, a.month, COUNT(*) AS active_customers,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM c c2 WHERE c2.cohort = c.cohort), 1) AS active_pct
FROM c JOIN a ON a.customer_id = c.customer_id
GROUP BY c.cohort, a.month;
