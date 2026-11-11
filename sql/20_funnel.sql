DROP VIEW IF EXISTS v_funnel CASCADE;

CREATE VIEW v_funnel AS
WITH ev AS (
  SELECT transaction_id,
         BOOL_OR(event_type = 'SENT_TO_PSP') AS has_sent,
         BOOL_OR(event_type = 'ISSUER_RESPONSE') AS has_issuer,
         BOOL_OR(event_type = 'FINAL_STATUS') AS has_final,
         MIN(event_timestamp) FILTER (WHERE event_type = 'INITIATED') AS t_init,
         MIN(event_timestamp) FILTER (WHERE event_type = 'SENT_TO_PSP') AS t_sent,
         MIN(event_timestamp) FILTER (WHERE event_type = 'ISSUER_RESPONSE') AS t_issuer,
         MIN(event_timestamp) FILTER (WHERE event_type = 'FINAL_STATUS') AS t_final
  FROM fact_payment_events GROUP BY transaction_id
)
SELECT t.transaction_id, t.status, t.error_code, t.network_type, t.initiated_at,
       b.size_tier, p.psp_name, c.category,
       ev.has_sent, ev.has_issuer, ev.has_final,
       CASE WHEN NOT ev.has_sent THEN '1: stopped at platform'
            WHEN NOT ev.has_final THEN '2: no final status'
            WHEN NOT ev.has_issuer THEN '3: no issuer response'
            ELSE '4: full lifecycle' END AS stop_point,
       EXTRACT(EPOCH FROM (ev.t_issuer - ev.t_sent)) * 1000 AS ms_psp_to_issuer,
       EXTRACT(EPOCH FROM (ev.t_final - ev.t_issuer)) * 1000 AS ms_issuer_to_final
FROM fact_transactions t
JOIN ev ON ev.transaction_id = t.transaction_id
JOIN dim_banks b ON b.bank_id = t.bank_id
JOIN dim_psp p ON p.psp_id = t.psp_id
LEFT JOIN dim_failure_codes c ON c.error_code = t.error_code;
