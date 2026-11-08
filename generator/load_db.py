import io
import os
import time
import dotenv
import pandas as pd
import psycopg2

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv.load_dotenv(os.path.join(PROJECT_DIR, ".env"))

# 4a. Connect to paymentiq database with psycopg2 (autocommit off)
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "paymentiq"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "123456"),
)
conn.autocommit = False
cur = conn.cursor()

# 4b. Execute sql/02_truth_tables.sql, then TRUNCATE
with open(os.path.join(PROJECT_DIR, "sql", "02_truth_tables.sql"), "r", encoding="utf-8") as f:
    truth_sql = f.read()
cur.execute(truth_sql)

cur.execute(
    "TRUNCATE fact_payment_events, fact_reconciliation, fact_transactions, staging.stg_transactions, truth.transaction_truth CASCADE;"
)
conn.commit()
print("Executed 02_truth_tables.sql and truncated fact/staging tables.")

# 4c. Define helper copy_csv
def copy_csv(path, table, columns, int_cols=None, fix_func=None):
    t0 = time.time()
    full_path = os.path.join(PROJECT_DIR, path)
    df = pd.read_csv(full_path, dtype=str)
    if fix_func is not None:
        df = fix_func(df)
    if int_cols:
        for c in int_cols:
            df[c] = pd.to_numeric(df[c]).astype("Int64")
    df = df[columns]
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    cols_str = ", ".join(columns)
    sql = f"COPY {table} ({cols_str}) FROM STDIN WITH (FORMAT csv)"
    cur.copy_expert(sql, buf)
    dt = time.time() - t0
    print(f"{table}: {len(df):,} rows loaded in {dt:.2f}s")
    return len(df)

# 4d. Load in order, then commit
txn_cols = [
    "transaction_id", "customer_id", "payee_id", "payee_category", "bank_id",
    "psp_id", "amount", "status", "error_code", "initiated_at",
    "completed_at", "latency_ms", "device_type", "network_type", "channel"
]
txn_int_cols = ["transaction_id", "customer_id", "payee_id", "bank_id", "psp_id", "latency_ms"]

counts = {}

# 1. fact_transactions
counts["fact_transactions"] = copy_csv(
    "data/processed/transactions_clean.csv",
    "fact_transactions",
    txn_cols,
    txn_int_cols
)

# 2. fact_payment_events
counts["fact_payment_events"] = copy_csv(
    "data/processed/payment_events_clean.csv",
    "fact_payment_events",
    ["event_id", "transaction_id", "event_type", "event_timestamp"],
    ["event_id", "transaction_id"]
)

# 3. fact_reconciliation
counts["fact_reconciliation"] = copy_csv(
    "data/raw/reconciliation.csv",
    "fact_reconciliation",
    ["transaction_id", "final_status", "settled_amount", "settlement_time"],
    ["transaction_id"]
)

# 4. staging.stg_transactions
counts["staging.stg_transactions"] = copy_csv(
    "data/raw/stg_transactions.csv",
    "staging.stg_transactions",
    txn_cols,
    txn_int_cols
)

# 5. truth.transaction_truth
counts["truth.transaction_truth"] = copy_csv(
    "data/raw/transaction_truth.csv",
    "truth.transaction_truth",
    ["transaction_id", "intent_id", "is_duplicate_debit", "incident_id"],
    ["transaction_id", "intent_id"]
)

# 6. truth.intent_truth
counts["truth.intent_truth"] = copy_csv(
    "data/raw/intent_truth.csv",
    "truth.intent_truth",
    ["intent_id", "customer_id", "repeat_of_intent_id", "first_status", "n_attempts", "final_outcome"],
    ["intent_id", "customer_id", "repeat_of_intent_id", "n_attempts"]
)

# 7. truth.recon_truth
counts["truth.recon_truth"] = copy_csv(
    "data/raw/recon_truth.csv",
    "truth.recon_truth",
    ["transaction_id", "mismatch_type"],
    ["transaction_id"]
)

# 8. truth.dq_truth
def fix_dq_truth(df):
    mask = df["issue_type"] == "MISSING_LATENCY"
    df.loc[mask, "true_value"] = df.loc[mask, "true_value"].astype(str).str.removesuffix(".0")
    return df

counts["truth.dq_truth"] = copy_csv(
    "data/raw/dq_truth.csv",
    "truth.dq_truth",
    ["transaction_id", "issue_type", "true_value"],
    ["transaction_id"],
    fix_func=fix_dq_truth
)

# 9. truth.attempt_truth
counts["truth.attempt_truth"] = copy_csv(
    "data/raw/attempt_truth_all.csv",
    "truth.attempt_truth",
    ["transaction_id", "intent_id", "attempt_number", "was_debited", "original_status"],
    ["transaction_id", "intent_id", "attempt_number"]
)

conn.commit()
print("All 9 tables loaded and committed.")

# 4e. CHECK LOAD: for each of the 9 tables assert that SELECT COUNT(*) equals CSV row count
# Also assert that SUM(amount) in fact_transactions equals the sum of the amount column of transactions_clean.csv (compare rounded to 2 decimals)
for tbl, exp_count in counts.items():
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    db_count = cur.fetchone()[0]
    assert db_count == exp_count, f"Count mismatch for {tbl}: DB {db_count} != CSV {exp_count}"
    print(f"PASS: {tbl} row count = {db_count:,}")

cur.execute("SELECT ROUND(SUM(amount)::numeric, 2) FROM fact_transactions")
db_sum = float(cur.fetchone()[0])
clean_txns = pd.read_csv(os.path.join(PROJECT_DIR, "data/processed/transactions_clean.csv"))
csv_sum = round(float(clean_txns["amount"].sum()), 2)
assert round(db_sum, 2) == csv_sum, f"Amount sum mismatch: DB {db_sum} != CSV {csv_sum}"
print(f"PASS: fact_transactions SUM(amount) = {db_sum:.2f} matches CSV ({csv_sum:.2f})")

# 4f. executes sql/03_indexes.sql, then runs ANALYZE ...
with open(os.path.join(PROJECT_DIR, "sql", "03_indexes.sql"), "r", encoding="utf-8") as f:
    indexes_sql = f.read()
cur.execute(indexes_sql)

cur.execute("ANALYZE fact_transactions, fact_payment_events, fact_reconciliation, truth.transaction_truth, truth.attempt_truth;")
conn.commit()
print("Indexes created and ANALYZE committed.")

# 4g & 4h. runs sql/04_validation.sql split on lines starting with "-- CHECK:"
validation_output_lines = []

def val_print(text=""):
    print(text)
    validation_output_lines.append(text)

with open(os.path.join(PROJECT_DIR, "sql", "04_validation.sql"), "r", encoding="utf-8") as f:
    val_sql = f.read()

raw_blocks = val_sql.split("-- CHECK:")
for b in raw_blocks[1:]:
    block_text = "-- CHECK:" + b
    lines = block_text.strip().splitlines()
    
    check_name = lines[0].replace("--", "").strip()
    comment_lines = [l.strip() for l in lines if l.strip().startswith("--")]
    query_lines = [l for l in lines if not l.strip().startswith("--")]
    query = "\n".join(query_lines).strip()
    
    val_print(f"=== {check_name} ===")
    for c in comment_lines:
        val_print(c)
    
    cur.execute(query)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    df_res = pd.DataFrame(rows, columns=cols)
    val_print(df_res.to_string(index=False))
    val_print("")

reports_path = os.path.join(PROJECT_DIR, "reports", "phase2_validation_output.txt")
os.makedirs(os.path.dirname(reports_path), exist_ok=True)
with open(reports_path, "w", encoding="utf-8") as f:
    f.write("\n".join(validation_output_lines))

conn.close()

# 4i. prints "Database load OK"
print("Database load OK")

