DROP VIEW IF EXISTS v_value_bands CASCADE;
DROP VIEW IF EXISTS v_latency_bands CASCADE;

-- Wilson 95 pct interval for a proportion k/n, returned as percentages
CREATE OR REPLACE FUNCTION wilson_lo(k numeric, n numeric) RETURNS numeric AS $$
  SELECT CASE WHEN n = 0 THEN NULL ELSE ROUND(100 * ((k/n + 1.9208/n - 1.96 * SQRT((k/n*(1-k/n) + 0.9604/n)/n)) / (1 + 3.8416/n)), 2) END
$$ LANGUAGE SQL IMMUTABLE;

CREATE OR REPLACE FUNCTION wilson_hi(k numeric, n numeric) RETURNS numeric AS $$
  SELECT CASE WHEN n = 0 THEN NULL ELSE ROUND(100 * ((k/n + 1.9208/n + 1.96 * SQRT((k/n*(1-k/n) + 0.9604/n)/n)) / (1 + 3.8416/n)), 2) END
$$ LANGUAGE SQL IMMUTABLE;

CREATE VIEW v_value_bands AS
SELECT CASE WHEN amount < 100 THEN '1: under 100'
            WHEN amount < 500 THEN '2: 100-499'
            WHEN amount < 2000 THEN '3: 500-1999'
            WHEN amount < 5000 THEN '4: 2000-4999'
            WHEN amount < 10000 THEN '5: 5000-9999'
            WHEN amount < 25000 THEN '6: 10000-24999'
            ELSE '7: 25000 and above' END AS value_band,
       status, error_code, is_first_attempt, amount
FROM v_attempts_eligible;

CREATE VIEW v_latency_bands AS
SELECT CASE WHEN latency_ms < 2000 THEN '1: under 2s'
            WHEN latency_ms < 5000 THEN '2: 2-5s'
            WHEN latency_ms < 10000 THEN '3: 5-10s'
            ELSE '4: 10s and above' END AS latency_band,
       status, error_code, network_type, is_first_attempt, latency_ms
FROM v_attempts_eligible;
