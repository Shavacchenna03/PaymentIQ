DROP VIEW IF EXISTS v_bank_conc CASCADE;

CREATE VIEW v_bank_conc AS
WITH agg AS (
  SELECT 'all' AS population, b.bank_id, b.bank_name, b.size_tier,
         COUNT(*) AS attempts,
         COUNT(*) FILTER (WHERE e.status = 'FAILED') AS failures
  FROM v_attempts_eligible e
  JOIN dim_banks b ON b.bank_id = e.bank_id
  GROUP BY b.bank_id, b.bank_name, b.size_tier
  UNION ALL
  SELECT 'first', b.bank_id, b.bank_name, b.size_tier,
         COUNT(*),
         COUNT(*) FILTER (WHERE e.status = 'FAILED')
  FROM v_attempts_eligible e
  JOIN dim_banks b ON b.bank_id = e.bank_id
  WHERE e.is_first_attempt
  GROUP BY b.bank_id, b.bank_name, b.size_tier
), s AS (
  SELECT agg.*,
         SUM(attempts) OVER p AS tot_attempts,
         SUM(failures) OVER p AS tot_failures,
         SUM(attempts) OVER pt AS tier_attempts,
         SUM(failures) OVER pt AS tier_failures
  FROM agg
  WINDOW p AS (PARTITION BY population),
         pt AS (PARTITION BY population, size_tier)
)
SELECT population, bank_id, bank_name, size_tier, attempts, failures,
       ROUND(100.0 * failures / attempts, 2) AS failure_pct,
       wilson_lo(failures, attempts) AS ci_low,
       wilson_hi(failures, attempts) AS ci_high,
       ROUND(100.0 * attempts / tot_attempts, 2) AS volume_share_pct,
       ROUND(100.0 * failures / tot_failures, 2) AS failure_share_pct,
       ROUND(failures - attempts::numeric * tot_failures / tot_attempts, 1) AS excess_vs_system,
       ROUND(100.0 * failures / attempts - 100.0 * tier_failures / tier_attempts, 2) AS rate_gap_vs_tier_pp,
       ROUND((failures - attempts * (tier_failures::numeric / tier_attempts))
             / NULLIF(SQRT(attempts * (tier_failures::numeric / tier_attempts) * (1 - tier_failures::numeric / tier_attempts)), 0), 2) AS z_vs_tier
FROM s;
