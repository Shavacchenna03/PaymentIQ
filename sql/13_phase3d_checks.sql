-- CHECK: 01 failure rate by value band, all eligible attempts, with 95 pct interval
-- EXPECT: roughly flat up to 10000, higher above; top bands have wide intervals
SELECT value_band, COUNT(*) AS attempts, COUNT(*) FILTER (WHERE status = 'FAILED') AS failures,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct,
       wilson_lo(COUNT(*) FILTER (WHERE status = 'FAILED'), COUNT(*)) AS ci_low,
       wilson_hi(COUNT(*) FILTER (WHERE status = 'FAILED'), COUNT(*)) AS ci_high
FROM v_value_bands GROUP BY value_band ORDER BY value_band;

-- CHECK: 02 limit and risk failures by value band
-- EXPECT: LIM_02 appears only at the top bands; risk blocks about 2 times higher from 10000
SELECT value_band, COUNT(*) AS attempts,
       COUNT(*) FILTER (WHERE error_code LIKE 'LIM%') AS limit_failures,
       COUNT(*) FILTER (WHERE error_code LIKE 'RSK%') AS risk_failures,
       ROUND(100.0 * COUNT(*) FILTER (WHERE error_code LIKE 'RSK%') / COUNT(*), 3) AS risk_pct
FROM v_value_bands GROUP BY value_band ORDER BY value_band;

-- CHECK: 03 failure rate by value band, excluding customer-side codes
-- EXPECT: flatter than check 01 because wrong PIN and insufficient funds do not depend on amount in this data
SELECT value_band, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED' AND error_code NOT LIKE 'CUS%' AND error_code <> 'BNK_03') / COUNT(*), 2) AS failure_pct_no_customer_codes
FROM v_value_bands GROUP BY value_band ORDER BY value_band;

-- CHECK: 04 latency view 1, all eligible attempts
-- EXPECT: about 5 pct under 5s, about 18 pct at 5-10s, over 90 pct at 10s and above
SELECT latency_band, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct,
       wilson_lo(COUNT(*) FILTER (WHERE status = 'FAILED'), COUNT(*)) AS ci_low,
       wilson_hi(COUNT(*) FILTER (WHERE status = 'FAILED'), COUNT(*)) AS ci_high
FROM v_latency_bands GROUP BY latency_band ORDER BY latency_band;

-- CHECK: 05 latency view 2, timeout failures (NET_01, NET_02, NET_03) removed
-- EXPECT: under 2s and 2-5s about 4 to 5 pct; 5-10s much lower than view 1; 10s and above still elevated because BNK_04 and CUS_05 are slow but not timeout codes
SELECT latency_band, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct,
       wilson_lo(COUNT(*) FILTER (WHERE status = 'FAILED'), COUNT(*)) AS ci_low,
       wilson_hi(COUNT(*) FILTER (WHERE status = 'FAILED'), COUNT(*)) AS ci_high
FROM v_latency_bands
WHERE NOT (status = 'FAILED' AND error_code IN ('NET_01','NET_02','NET_03'))
GROUP BY latency_band ORDER BY latency_band;

-- CHECK: 06 share of each latency band's failures that are timeouts
-- EXPECT: timeouts make up most of the failures in the 5-10s and 10s+ bands
SELECT latency_band,
       COUNT(*) FILTER (WHERE status = 'FAILED') AS failures,
       COUNT(*) FILTER (WHERE status = 'FAILED' AND error_code IN ('NET_01','NET_02','NET_03')) AS timeout_failures,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED' AND error_code IN ('NET_01','NET_02','NET_03'))
             / NULLIF(COUNT(*) FILTER (WHERE status = 'FAILED'), 0), 1) AS timeout_share_pct
FROM v_latency_bands GROUP BY latency_band ORDER BY latency_band;

-- CHECK: 07 latency view 3, 4G only, timeouts removed
-- EXPECT: same shape as check 05 on a single network type
SELECT latency_band, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct
FROM v_latency_bands
WHERE network_type = '4G' AND NOT (status = 'FAILED' AND error_code IN ('NET_01','NET_02','NET_03'))
GROUP BY latency_band ORDER BY latency_band;
