DROP SCHEMA IF EXISTS truth CASCADE;
DROP SCHEMA IF EXISTS staging CASCADE;
DROP TABLE IF EXISTS fact_reconciliation CASCADE;
DROP TABLE IF EXISTS fact_payment_events CASCADE;
DROP TABLE IF EXISTS fact_transactions CASCADE;
DROP TABLE IF EXISTS dim_customers CASCADE;
DROP TABLE IF EXISTS dim_failure_codes CASCADE;
DROP TABLE IF EXISTS dim_psp CASCADE;
DROP TABLE IF EXISTS dim_banks CASCADE;

CREATE SCHEMA staging;
CREATE SCHEMA truth;

CREATE TABLE dim_banks (
    bank_id     INTEGER PRIMARY KEY,
    bank_name   TEXT NOT NULL UNIQUE,
    bank_type   TEXT NOT NULL,
    size_tier   TEXT NOT NULL CHECK (size_tier IN ('Large','Medium','Small'))
);

CREATE TABLE dim_psp (
    psp_id        INTEGER PRIMARY KEY,
    psp_name      TEXT NOT NULL UNIQUE,
    provider_type TEXT NOT NULL
);

CREATE TABLE dim_failure_codes (
    error_code  TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    description TEXT NOT NULL,
    retry_class TEXT NOT NULL CHECK (retry_class IN
        ('Safe retry','Customer action','Verify status first','Do not retry','Escalate'))
);

CREATE TABLE dim_customers (
    customer_id         INTEGER PRIMARY KEY,
    signup_date         DATE NOT NULL,
    city_tier           TEXT NOT NULL CHECK (city_tier IN ('Tier1','Tier2','Tier3')),
    primary_device      TEXT NOT NULL CHECK (primary_device IN ('Android','iOS','Web')),
    acquisition_channel TEXT NOT NULL
);

CREATE TABLE fact_transactions (
    transaction_id BIGINT PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES dim_customers(customer_id),
    payee_id       INTEGER NOT NULL,
    payee_category TEXT NOT NULL,
    bank_id        INTEGER NOT NULL REFERENCES dim_banks(bank_id),
    psp_id         INTEGER NOT NULL REFERENCES dim_psp(psp_id),
    amount         NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    status         TEXT NOT NULL CHECK (status IN ('SUCCESS','FAILED','PENDING')),
    error_code     TEXT REFERENCES dim_failure_codes(error_code),
    initiated_at   TIMESTAMP NOT NULL,
    completed_at   TIMESTAMP,
    latency_ms     INTEGER CHECK (latency_ms >= 0),
    device_type    TEXT NOT NULL CHECK (device_type IN ('Android','iOS','Web')),
    network_type   TEXT NOT NULL CHECK (network_type IN ('WiFi','5G','4G','3G','2G')),
    channel        TEXT NOT NULL,
    CHECK (completed_at IS NULL OR completed_at >= initiated_at),
    CHECK ((status = 'FAILED' AND error_code IS NOT NULL)
        OR (status IN ('SUCCESS','PENDING') AND error_code IS NULL))
);

CREATE TABLE fact_payment_events (
    event_id        BIGINT PRIMARY KEY,
    transaction_id  BIGINT NOT NULL REFERENCES fact_transactions(transaction_id),
    event_type      TEXT NOT NULL CHECK (event_type IN
        ('INITIATED','SENT_TO_PSP','ISSUER_RESPONSE','FINAL_STATUS')),
    event_timestamp TIMESTAMP NOT NULL
);

CREATE TABLE fact_reconciliation (
    transaction_id  BIGINT PRIMARY KEY REFERENCES fact_transactions(transaction_id),
    final_status    TEXT NOT NULL CHECK (final_status IN ('SUCCESS','FAILED','PENDING')),
    settled_amount  NUMERIC(12,2) NOT NULL CHECK (settled_amount >= 0),
    settlement_time TIMESTAMP
);

-- Staging: raw landing table, same columns, NO constraints, so dirty data can load
CREATE TABLE staging.stg_transactions (
    transaction_id BIGINT,
    customer_id    INTEGER,
    payee_id       INTEGER,
    payee_category TEXT,
    bank_id        INTEGER,
    psp_id         INTEGER,
    amount         NUMERIC(12,2),
    status         TEXT,
    error_code     TEXT,
    initiated_at   TIMESTAMP,
    completed_at   TIMESTAMP,
    latency_ms     INTEGER,
    device_type    TEXT,
    network_type   TEXT,
    channel        TEXT
);

-- Truth: hidden answer key, never queried until the final comparison
CREATE TABLE truth.customer_truth (
    customer_id  INTEGER PRIMARY KEY,
    true_segment TEXT NOT NULL
);

CREATE TABLE truth.transaction_truth (
    transaction_id     BIGINT PRIMARY KEY,
    intent_id          BIGINT NOT NULL,
    is_duplicate_debit BOOLEAN NOT NULL DEFAULT FALSE,
    incident_id        TEXT
);
