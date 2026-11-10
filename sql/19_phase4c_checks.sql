-- CHECK: 01 view totals
-- EXPECT: 273574 first attempts, 24772 failures
SELECT COUNT(*) AS attempts, COUNT(*) FILTER (WHERE status = 'FAILED') AS failures FROM v_first_rc;

-- CHECK: 02 network mix by bank group
-- EXPECT: slow (3G and 2G) share roughly Tarang 25 to 30 pct, Other Large about 15, Zenora about 5 to 9; Zenora fast share highest
SELECT bank_group, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE network_group = 'fast') / COUNT(*), 1) AS fast_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE network_group = '4G') / COUNT(*), 1) AS g4_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE network_group = 'slow') / COUNT(*), 1) AS slow_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct
FROM v_first_rc WHERE bank_group IN ('Tarang National','Zenora','Other Large')
GROUP BY bank_group ORDER BY bank_group;

-- CHECK: 03 failure rate by bank group within network group
-- EXPECT: within each network group Tarang and Other Large are close; Zenora is the highest or near highest in fast and 4G
SELECT bank_group, network_group, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct
FROM v_first_rc WHERE bank_group IN ('Tarang National','Zenora','Other Large')
GROUP BY bank_group, network_group ORDER BY network_group, bank_group;

-- CHECK: 04 bank-side failure rate by tier, peak (hours 20-21) versus other hours
-- EXPECT: Small about 2 times higher at peak, Medium about 1.2 times, Large about 1.1 times
SELECT size_tier, is_peak, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE category = 'Bank-side' AND error_code NOT IN ('BNK_03','BNK_05') AND NOT is_repaired_code) / COUNT(*), 2) AS bank_side_pct
FROM v_first_rc GROUP BY size_tier, is_peak ORDER BY size_tier, is_peak;

-- CHECK: 05 network-family failure rate by network type
-- EXPECT: 3G and 2G about 3.3 to 4.5 times WiFi and 5G
SELECT network_type, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE category = 'Network' AND NOT is_repaired_code) / COUNT(*), 2) AS network_family_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct
FROM v_first_rc GROUP BY network_type ORDER BY network_family_pct;

-- CHECK: 06 PSP breakdown
-- EXPECT: Clearwave has the highest PSP-side rate; other PSPs similar
SELECT psp_name, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE category = 'PSP-side' AND NOT is_repaired_code) / COUNT(*), 2) AS psp_side_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE error_code = 'PSP_01') / COUNT(*), 2) AS psp_01_pct
FROM v_first_rc GROUP BY psp_name ORDER BY psp_side_pct DESC;

-- CHECK: 07 Clearwave PSP_01 rate inside versus outside the window found in 3E (3 to 16 Aug)
-- EXPECT: about 12 pct inside, under 1 pct outside
SELECT (attempt_date BETWEEN DATE '2026-08-03' AND DATE '2026-08-16') AS in_window, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE error_code = 'PSP_01') / COUNT(*), 2) AS psp_01_pct
FROM v_first_rc WHERE psp_name = 'Clearwave' GROUP BY 1 ORDER BY 1;

-- CHECK: 08 device type
-- EXPECT: failure rates within about 0.3 points of each other (descriptive only, tested in 4E)
SELECT device_type, COUNT(*) AS attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'FAILED') / COUNT(*), 2) AS failure_pct
FROM v_first_rc GROUP BY device_type ORDER BY device_type;
