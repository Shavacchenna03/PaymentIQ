DROP INDEX IF EXISTS idx_txn_initiated_at;
DROP INDEX IF EXISTS idx_txn_bank;
DROP INDEX IF EXISTS idx_txn_psp;
DROP INDEX IF EXISTS idx_txn_customer_time;
DROP INDEX IF EXISTS idx_txn_status;
DROP INDEX IF EXISTS idx_txn_error_code;
DROP INDEX IF EXISTS idx_events_txn;
DROP INDEX IF EXISTS truth.idx_txntruth_intent;
DROP INDEX IF EXISTS truth.idx_attempttruth_intent;

CREATE INDEX idx_txn_initiated_at ON fact_transactions (initiated_at);
CREATE INDEX idx_txn_bank ON fact_transactions (bank_id);
CREATE INDEX idx_txn_psp ON fact_transactions (psp_id);
CREATE INDEX idx_txn_customer_time ON fact_transactions (customer_id, initiated_at);
CREATE INDEX idx_txn_status ON fact_transactions (status);
CREATE INDEX idx_txn_error_code ON fact_transactions (error_code);
CREATE INDEX idx_events_txn ON fact_payment_events (transaction_id);
CREATE INDEX idx_txntruth_intent ON truth.transaction_truth (intent_id);
CREATE INDEX idx_attempttruth_intent ON truth.attempt_truth (intent_id);

