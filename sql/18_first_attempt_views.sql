DROP VIEW IF EXISTS v_first_rc CASCADE;

CREATE VIEW v_first_rc AS
SELECT a.transaction_id, a.customer_id, a.amount, a.status, a.error_code,
       a.initiated_at, a.attempt_date, a.latency_ms, a.network_type, a.device_type,
       a.is_repaired_code, b.bank_name, b.size_tier, p.psp_name, c.category,
       CASE WHEN b.bank_name = 'Tarang National' THEN 'Tarang National'
            WHEN b.bank_name = 'Zenora' THEN 'Zenora'
            WHEN b.size_tier = 'Large' THEN 'Other Large'
            ELSE b.size_tier END AS bank_group,
       CASE WHEN a.network_type IN ('WiFi','5G') THEN 'fast'
            WHEN a.network_type = '4G' THEN '4G'
            ELSE 'slow' END AS network_group,
       (EXTRACT(HOUR FROM a.initiated_at) IN (20, 21)) AS is_peak
FROM v_attempts_rc a
JOIN dim_banks b ON b.bank_id = a.bank_id
JOIN dim_psp p ON p.psp_id = a.psp_id
LEFT JOIN dim_failure_codes c ON c.error_code = a.error_code
WHERE a.is_first_attempt;
