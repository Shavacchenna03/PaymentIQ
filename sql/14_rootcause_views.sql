DROP VIEW IF EXISTS v_failures_coded CASCADE;
DROP VIEW IF EXISTS v_attempts_rc CASCADE;
DROP VIEW IF EXISTS v_repaired_codes CASCADE;

-- Rows whose error code was missing in the raw staging data and mapped to UNK_01 by cleaning
CREATE VIEW v_repaired_codes AS
SELECT DISTINCT transaction_id
FROM staging.stg_transactions
WHERE status = 'FAILED' AND error_code IS NULL;

-- Eligible attempts with a flag for repaired codes (denominator for cause-specific models)
CREATE VIEW v_attempts_rc AS
SELECT e.*, (r.transaction_id IS NOT NULL) AS is_repaired_code
FROM v_attempts_eligible e
LEFT JOIN v_repaired_codes r ON r.transaction_id = e.transaction_id;

-- Failures with a trustworthy code, joined to the taxonomy
CREATE VIEW v_failures_coded AS
SELECT a.*, c.category, c.description, c.retry_class
FROM v_attempts_rc a
JOIN dim_failure_codes c ON c.error_code = a.error_code
WHERE a.status = 'FAILED' AND NOT a.is_repaired_code;
