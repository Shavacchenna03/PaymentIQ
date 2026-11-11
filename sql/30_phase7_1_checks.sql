-- CHECK: 01 decision table size
-- EXPECT: about 27000 to 27300 rows (failed journey starts 25805 plus pending starts); five decisions
SELECT COUNT(*) AS rows, COUNT(DISTINCT decision) AS decisions, COUNT(*) FILTER (WHERE status = 'PENDING') AS pending_rows FROM decision_table;

-- CHECK: 02 decisions: volume, value and what customers actually did (observed, self-selected)
-- EXPECT: Wait for status confirmation largest (about 17000); Eligible for retry evaluation about 6000 to 7500; observed recovery highest for Eligible and lowest for Customer action and Do not retry
SELECT decision, COUNT(*) AS journeys, ROUND(SUM(amount) / 100000.0, 1) AS value_lakh,
       ROUND(100.0 * COUNT(*) FILTER (WHERE n_attempts > 1) / COUNT(*), 1) AS retried_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE any_success) / COUNT(*), 1) AS recovered_pct
FROM decision_table GROUP BY decision ORDER BY journeys DESC;

-- CHECK: 03 hard-rule audit (every count must be 0)
-- EXPECT: all four values 0
SELECT COUNT(*) FILTER (WHERE decision = 'Eligible for retry evaluation' AND retry_class <> 'Safe retry') AS eligible_not_safe,
       COUNT(*) FILTER (WHERE decision = 'Eligible for retry evaluation' AND status = 'PENDING') AS eligible_but_pending,
       COUNT(*) FILTER (WHERE decision = 'Eligible for retry evaluation' AND error_code IN ('CUS_03','TEC_01','RSK_01')) AS eligible_do_not_retry,
       COUNT(*) FILTER (WHERE decision = 'Eligible for retry evaluation' AND in_incident) AS eligible_in_incident
FROM decision_table;

-- CHECK: 04 duplicate-debit exposure by decision (answer key: money had already moved)
-- EXPECT: about 900 to 1000 journey starts where the customer was already debited; none in Eligible for retry evaluation
SELECT d.decision, COUNT(*) AS already_debited_starts, ROUND(SUM(d.amount) / 100000.0, 2) AS value_lakh
FROM decision_table d
JOIN truth.attempt_truth a ON a.transaction_id = d.transaction_id
WHERE a.was_debited OR (d.status = 'PENDING' AND a.original_status = 'SUCCESS')
GROUP BY d.decision ORDER BY 2 DESC;

-- CHECK: 05 incident detector scored against the planted outage rows (attempt level, answer key)
-- EXPECT: flagged_blocks a handful; false_blocks_other_banks 0 to 2; recall about 60 to 90 pct (outage hours that fall in partly affected blocks are missed); precision above 60 pct
SELECT (SELECT COUNT(*) FROM incident_blocks WHERE is_incident) AS flagged_blocks,
       (SELECT COUNT(*) FROM incident_blocks ib JOIN dim_banks b ON b.bank_id = ib.bank_id WHERE ib.is_incident AND b.bank_name <> 'Kestrel Commercial') AS false_blocks_other_banks,
       COUNT(*) FILTER (WHERE ib.is_incident) AS flagged_attempts,
       COUNT(*) FILTER (WHERE t.incident_id = 'P1_OUTAGE') AS true_outage_attempts,
       COUNT(*) FILTER (WHERE ib.is_incident AND t.incident_id = 'P1_OUTAGE') AS tp_attempts,
       ROUND(100.0 * COUNT(*) FILTER (WHERE ib.is_incident AND t.incident_id = 'P1_OUTAGE') / NULLIF(COUNT(*) FILTER (WHERE t.incident_id = 'P1_OUTAGE'), 0), 1) AS recall_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE ib.is_incident AND t.incident_id = 'P1_OUTAGE') / NULLIF(COUNT(*) FILTER (WHERE ib.is_incident), 0), 1) AS precision_pct
FROM v_attempts_eligible e
JOIN incident_blocks ib ON ib.bank_id = e.bank_id AND ib.d = e.attempt_date AND ib.blk = EXTRACT(HOUR FROM e.initiated_at)::int / 3
JOIN truth.transaction_truth t ON t.transaction_id = e.transaction_id;

-- CHECK: 06 what the incident hold changes (Safe retry class journey starts, observed)
-- EXPECT: inside incident blocks recovery far lower than outside (retries succeed 0.15 times as often); small counts
SELECT in_incident, COUNT(*) AS journeys,
       ROUND(100.0 * COUNT(*) FILTER (WHERE n_attempts > 1) / COUNT(*), 1) AS retried_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE any_success) / COUNT(*), 1) AS recovered_pct
FROM decision_table WHERE retry_class = 'Safe retry' AND status = 'FAILED' GROUP BY in_incident ORDER BY in_incident;

-- CHECK: 07 duplicate-debit detector scored against truth (attempt level)
-- EXPECT: truth 280; true positives about 225 to 250; precision about 85 to 92 pct; recall about 80 to 90 pct
SELECT COUNT(*) FILTER (WHERE d.transaction_id IS NOT NULL) AS flagged,
       COUNT(*) FILTER (WHERE t.is_duplicate_debit) AS truth_duplicates,
       COUNT(*) FILTER (WHERE d.transaction_id IS NOT NULL AND t.is_duplicate_debit) AS tp,
       COUNT(*) FILTER (WHERE d.transaction_id IS NOT NULL AND NOT t.is_duplicate_debit) AS fp,
       COUNT(*) FILTER (WHERE d.transaction_id IS NULL AND t.is_duplicate_debit) AS fn,
       ROUND(100.0 * COUNT(*) FILTER (WHERE d.transaction_id IS NOT NULL AND t.is_duplicate_debit) / NULLIF(COUNT(*) FILTER (WHERE d.transaction_id IS NOT NULL), 0), 1) AS precision_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE d.transaction_id IS NOT NULL AND t.is_duplicate_debit) / NULLIF(COUNT(*) FILTER (WHERE t.is_duplicate_debit), 0), 1) AS recall_pct,
       ROUND(SUM(f.amount) FILTER (WHERE d.transaction_id IS NOT NULL AND t.is_duplicate_debit) / 100000.0, 2) AS caught_lakh
FROM fact_transactions f
JOIN truth.transaction_truth t ON t.transaction_id = f.transaction_id
LEFT JOIN v_dup_detect d ON d.transaction_id = f.transaction_id;

-- CHECK: 08 why the detector misses and why it raises false alarms
-- EXPECT: misses mostly "earlier attempt still PENDING at the bank" (about 30 to 40); false alarms mostly RANDOM_SETTLED_FAILED or NONE rows from merged repeat purchases
SELECT 'miss' AS kind,
       CASE WHEN EXISTS (SELECT 1 FROM truth.attempt_truth a2 JOIN truth.recon_truth r2 ON r2.transaction_id = a2.transaction_id
                         WHERE a2.intent_id = a.intent_id AND a2.attempt_number < a.attempt_number AND r2.mismatch_type = 'PENDING_UNRESOLVED')
            THEN 'earlier attempt still PENDING at the bank' ELSE 'other (for example split from its journey)' END AS reason,
       COUNT(*) AS n
FROM truth.transaction_truth t
JOIN truth.attempt_truth a ON a.transaction_id = t.transaction_id
LEFT JOIN v_dup_detect d ON d.transaction_id = t.transaction_id
WHERE t.is_duplicate_debit AND d.transaction_id IS NULL
GROUP BY 2
UNION ALL
SELECT 'false alarm', r.mismatch_type, COUNT(*)
FROM v_dup_detect d
JOIN truth.transaction_truth t ON t.transaction_id = d.transaction_id
JOIN truth.recon_truth r ON r.transaction_id = d.transaction_id
WHERE NOT t.is_duplicate_debit
GROUP BY r.mismatch_type
ORDER BY 1, 3 DESC;
