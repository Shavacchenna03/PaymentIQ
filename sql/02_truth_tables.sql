DROP TABLE IF EXISTS truth.intent_truth;
DROP TABLE IF EXISTS truth.recon_truth;
DROP TABLE IF EXISTS truth.dq_truth;
DROP TABLE IF EXISTS truth.attempt_truth;

CREATE TABLE truth.intent_truth (
    intent_id           BIGINT PRIMARY KEY,
    customer_id         INTEGER NOT NULL,
    repeat_of_intent_id BIGINT,
    first_status        TEXT NOT NULL CHECK (first_status IN ('SUCCESS','FAILED','PENDING')),
    n_attempts          INTEGER NOT NULL CHECK (n_attempts BETWEEN 1 AND 4),
    final_outcome       TEXT NOT NULL CHECK (final_outcome IN ('SUCCESS','NOT_SUCCESS'))
);

CREATE TABLE truth.recon_truth (
    transaction_id BIGINT PRIMARY KEY,
    mismatch_type  TEXT NOT NULL
);

CREATE TABLE truth.dq_truth (
    transaction_id BIGINT NOT NULL,
    issue_type     TEXT NOT NULL CHECK (issue_type IN ('MISSING_LATENCY','MISSING_ERROR_CODE','DUPLICATE_ROW')),
    true_value     TEXT
);

CREATE TABLE truth.attempt_truth (
    transaction_id  BIGINT PRIMARY KEY,
    intent_id       BIGINT NOT NULL,
    attempt_number  INTEGER NOT NULL CHECK (attempt_number BETWEEN 1 AND 4),
    was_debited     BOOLEAN NOT NULL,
    original_status TEXT
);

