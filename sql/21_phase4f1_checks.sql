-- CHECK: 01 funnel totals
-- EXPECT: 293991 attempts; full lifecycle about 93 pct; no issuer response about 6 pct; no final status about 0.5 pct; stopped at platform about 0.5 pct
SELECT stop_point, COUNT(*) AS attempts, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM v_funnel GROUP BY stop_point ORDER BY stop_point;

-- CHECK: 02 stop point by status
-- EXPECT: SUCCESS all full lifecycle; PENDING all no final status; FAILED split across the other points
SELECT status, stop_point, COUNT(*) AS attempts
FROM v_funnel GROUP BY status, stop_point ORDER BY status, stop_point;

-- CHECK: 03 stop point by failure code (compare with the taxonomy)
-- EXPECT: NET and PSP codes, RSK, CUS_04, CUS_05 mostly no issuer response; CUS_03, TEC_01, TEC_03 stopped at platform; bank codes full lifecycle
SELECT error_code, COUNT(*) AS failures,
       COUNT(*) FILTER (WHERE stop_point LIKE '1%') AS platform,
       COUNT(*) FILTER (WHERE stop_point LIKE '3%') AS no_issuer,
       COUNT(*) FILTER (WHERE stop_point LIKE '4%') AS full
FROM v_funnel WHERE status = 'FAILED' GROUP BY error_code ORDER BY failures DESC;

-- CHECK: 04 where failures stop, by category
-- EXPECT: Network and PSP-side almost entirely no issuer response; Bank-side almost entirely full lifecycle
SELECT COALESCE(category, 'none') AS category, COUNT(*) AS failures,
       ROUND(100.0 * COUNT(*) FILTER (WHERE stop_point LIKE '3%') / COUNT(*), 1) AS no_issuer_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE stop_point LIKE '1%') / COUNT(*), 1) AS platform_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE stop_point LIKE '4%') / COUNT(*), 1) AS full_pct
FROM v_funnel WHERE status = 'FAILED' GROUP BY category ORDER BY failures DESC;

-- CHECK: 05 share of attempts with no issuer response, by bank tier and by PSP
-- EXPECT: higher at Small banks (more network failures) and Clearwave (deploy window)
SELECT 'tier' AS dim, size_tier AS grp, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE stop_point LIKE '3%') / COUNT(*), 2) AS no_issuer_pct
FROM v_funnel GROUP BY size_tier
UNION ALL
SELECT 'psp', psp_name, COUNT(*),
       ROUND(100.0 * COUNT(*) FILTER (WHERE stop_point LIKE '3%') / COUNT(*), 2)
FROM v_funnel GROUP BY psp_name ORDER BY 1, 4 DESC;

-- CHECK: 06 step timing for SUCCESS attempts, by network type
-- EXPECT: PSP-to-issuer median grows from WiFi and 5G to 2G (about 3 times)
SELECT network_type, COUNT(*) AS attempts,
       ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY ms_psp_to_issuer))::numeric) AS median_psp_to_issuer_ms,
       ROUND((percentile_cont(0.95) WITHIN GROUP (ORDER BY ms_psp_to_issuer))::numeric) AS p95_psp_to_issuer_ms,
       ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY ms_issuer_to_final))::numeric) AS median_issuer_to_final_ms
FROM v_funnel WHERE status = 'SUCCESS' AND has_issuer
GROUP BY network_type ORDER BY median_psp_to_issuer_ms;

-- CHECK: 07 PENDING attempts and reconciliation outcome
-- EXPECT: 1508 PENDING; 1184 resolved, 324 unresolved
SELECT r.final_status, COUNT(*) AS pending_attempts
FROM v_funnel f JOIN fact_reconciliation r ON r.transaction_id = f.transaction_id
WHERE f.status = 'PENDING' GROUP BY r.final_status ORDER BY r.final_status;
