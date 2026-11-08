import os
import sys
import numpy as np
import pandas as pd

# a. Imports & RNG
sys.path.insert(0, os.path.dirname(__file__))
from config import *

rng = np.random.default_rng(SEED + 5)

# b. LOAD CSVs
raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

df_attempts = pd.read_csv(
    os.path.join(raw_dir, "attempts_all.csv"),
    parse_dates=["initiated_at", "completed_at"],
    keep_default_na=False
)
df_attempts["error_code"] = df_attempts["error_code"].replace("", np.nan)
df_attempts["completed_at"] = pd.to_datetime(df_attempts["completed_at"].replace("", np.nan))
df_attempts["latency_ms"] = pd.to_numeric(df_attempts["latency_ms"].replace("", np.nan), errors="coerce")

df_att_truth = pd.read_csv(
    os.path.join(raw_dir, "attempt_truth_all.csv"),
    keep_default_na=False
)
df_att_truth["was_debited"] = df_att_truth["was_debited"].astype(str).str.lower().isin(["true", "1"])

df_txn_truth = pd.read_csv(
    os.path.join(raw_dir, "transaction_truth.csv"),
    keep_default_na=False
)
df_txn_truth["is_duplicate_debit"] = df_txn_truth["is_duplicate_debit"].astype(str).str.lower().isin(["true", "1"])

# Merge attempt_truth_all onto attempts by transaction_id
df = df_attempts.merge(
    df_att_truth[["transaction_id", "intent_id", "attempt_number", "was_debited", "original_status"]],
    on="transaction_id",
    how="inner"
)
df = df.sort_values("transaction_id").reset_index(drop=True)
n = len(df)

assert n == len(df_attempts), f"Row count mismatch: {n} vs {len(df_attempts)}"
assert df["transaction_id"].notna().all(), "Missing transaction_id after merge"

# c. Random Draws in exact order
u_sent = rng.random(n)
u_issuer = rng.random(n)
u_pend = rng.random(n)
u_flip = rng.random(n)
u_lag_kind = rng.random(n)
u_lag = rng.random(n)
u_unres = rng.random(n)

# d. EVENTS
dur_ms = np.where(
    df["status"] != "PENDING",
    (df["completed_at"] - df["initiated_at"]).dt.total_seconds() * 1000.0,
    np.nan
)

# 1. INITIATED: every row
ev_init = pd.DataFrame({
    "transaction_id": df["transaction_id"],
    "event_type": "INITIATED",
    "event_timestamp": df["initiated_at"],
    "event_order": 1
})

# 2. SENT_TO_PSP: every row except status FAILED with error_code in NO_PSP_CODES
is_failed = (df["status"] == "FAILED").values
is_no_psp_code = df["error_code"].isin(NO_PSP_CODES).values
mask_sent = ~(is_failed & is_no_psp_code)

sent_frac = SENT_FRAC_RANGE[0] + u_sent * (SENT_FRAC_RANGE[1] - SENT_FRAC_RANGE[0])
sent_offset_non_pending = np.round(dur_ms * sent_frac)
sent_offset_pending = np.round(PENDING_SENT_OFFSET_MS[0] + u_pend * (PENDING_SENT_OFFSET_MS[1] - PENDING_SENT_OFFSET_MS[0]))
sent_offset_ms = np.where(df["status"] == "PENDING", sent_offset_pending, sent_offset_non_pending)

sent_ts = df["initiated_at"] + pd.to_timedelta(sent_offset_ms, unit="ms")

ev_sent = pd.DataFrame({
    "transaction_id": df.loc[mask_sent, "transaction_id"],
    "event_type": "SENT_TO_PSP",
    "event_timestamp": sent_ts[mask_sent],
    "event_order": 2
})

# 3. ISSUER_RESPONSE: non-PENDING, has SENT_TO_PSP, and not (FAILED with error_code in NO_ISSUER_CODES)
is_not_pending = (df["status"] != "PENDING").values
is_no_issuer_code = df["error_code"].isin(NO_ISSUER_CODES).values
mask_issuer = is_not_pending & mask_sent & ~(is_failed & is_no_issuer_code)

issuer_frac = ISSUER_FRAC_RANGE[0] + u_issuer * (ISSUER_FRAC_RANGE[1] - ISSUER_FRAC_RANGE[0])
issuer_offset_ms = np.round(dur_ms * issuer_frac)
issuer_ts = df["initiated_at"] + pd.to_timedelta(issuer_offset_ms, unit="ms")

ev_issuer = pd.DataFrame({
    "transaction_id": df.loc[mask_issuer, "transaction_id"],
    "event_type": "ISSUER_RESPONSE",
    "event_timestamp": issuer_ts[mask_issuer],
    "event_order": 3
})

# 4. FINAL_STATUS: every row that is not PENDING
mask_final = is_not_pending
ev_final = pd.DataFrame({
    "transaction_id": df.loc[mask_final, "transaction_id"],
    "event_type": "FINAL_STATUS",
    "event_timestamp": df.loc[mask_final, "completed_at"],
    "event_order": 4
})

# Concatenate, sort, assign event_id
events = pd.concat([ev_init, ev_sent, ev_issuer, ev_final], ignore_index=True)
events = events.sort_values(by=["event_timestamp", "transaction_id", "event_order"]).reset_index(drop=True)
events["event_id"] = np.arange(1, len(events) + 1, dtype=np.int64)
events = events.drop(columns=["event_order"])

# e. RECONCILIATION
final_status = df["status"].copy().values
mismatch_type = np.full(n, "NONE", dtype=object)

# Rule 1: DEBITED_TIMEOUT
mask_debited = (df["was_debited"] == True).values
final_status[mask_debited] = "SUCCESS"
mismatch_type[mask_debited] = "DEBITED_TIMEOUT"

# Rule 2: PENDING rows
mask_pending = (df["status"] == "PENDING").values
is_resolved = mask_pending & (u_unres < RECON_PENDING_RESOLVED_P)
is_unresolved = mask_pending & (~is_resolved)

orig_status = df["original_status"].values
final_status[is_resolved] = orig_status[is_resolved]
mismatch_type[is_resolved] = np.where(
    orig_status[is_resolved] == "SUCCESS",
    "PENDING_RESOLVED_SUCCESS",
    "PENDING_RESOLVED_FAILED"
)

final_status[is_unresolved] = "PENDING"
mismatch_type[is_unresolved] = "PENDING_UNRESOLVED"

# Rule 3: RANDOM_REVERSAL
mask_reversal = (df["status"] == "SUCCESS").values & (u_flip < RECON_REVERSAL_P)
final_status[mask_reversal] = "FAILED"
mismatch_type[mask_reversal] = "RANDOM_REVERSAL"

# Rule 4: RANDOM_SETTLED_FAILED
mask_settled_failed = (df["status"] == "FAILED").values & (~df["was_debited"].values) & (u_flip < RECON_SETTLED_FAILED_P)
final_status[mask_settled_failed] = "SUCCESS"
mismatch_type[mask_settled_failed] = "RANDOM_SETTLED_FAILED"

# settled_amount
settled_amount = np.where(final_status == "SUCCESS", df["amount"].values, 0.0)
settled_amount = np.round(settled_amount, 2)

# settlement_time
base_time = np.where(df["status"] == "PENDING", df["initiated_at"].values, df["completed_at"].values)
base_time_dt = pd.to_datetime(base_time)

lag_pending_succ = RECON_PENDING_LAG_H[0] + u_lag * (RECON_PENDING_LAG_H[1] - RECON_PENDING_LAG_H[0])
lag_late = RECON_LATE_LAG_H[0] + u_lag * (RECON_LATE_LAG_H[1] - RECON_LATE_LAG_H[0])
lag_normal = RECON_NORMAL_LAG_H[0] + u_lag * (RECON_NORMAL_LAG_H[1] - RECON_NORMAL_LAG_H[0])
lag_other = np.where(u_lag_kind < RECON_LATE_TAIL_P, lag_late, lag_normal)

lag_h = np.where(mismatch_type == "PENDING_RESOLVED_SUCCESS", lag_pending_succ, lag_other)
lag_seconds = np.round(lag_h * 3600.0).astype(np.int64)

settlement_time_all = base_time_dt + pd.to_timedelta(lag_seconds, unit="s")
settlement_time = pd.Series(settlement_time_all).where(final_status == "SUCCESS", pd.NaT)

df_recon = pd.DataFrame({
    "transaction_id": df["transaction_id"],
    "final_status": final_status,
    "settled_amount": settled_amount,
    "settlement_time": settlement_time
})

df_recon_truth = pd.DataFrame({
    "transaction_id": df["transaction_id"],
    "mismatch_type": mismatch_type
})

# f. ASSERTS
# 1. event_id unique
assert events["event_id"].is_unique, "event_id not unique"

# 2. every transaction_id in events exists in attempts
assert events["transaction_id"].isin(df["transaction_id"]).all(), "Unknown transaction_id in events"

# 3. each transaction has exactly one INITIATED event and at most one of each other event type
init_counts = events[events["event_type"] == "INITIATED"].groupby("transaction_id").size()
assert len(init_counts) == n and (init_counts == 1).all(), "Transactions must have exactly one INITIATED event"
assert (events.groupby(["transaction_id", "event_type"]).size() <= 1).all(), "Duplicate event_type within transaction"

# 4. within each transaction, timestamps non-decreasing in event order
assert (sent_ts[mask_sent].values >= df.loc[mask_sent, "initiated_at"].values).all(), "SENT_TO_PSP < INITIATED"
assert (issuer_ts[mask_issuer].values >= sent_ts[mask_issuer].values).all(), "ISSUER_RESPONSE < SENT_TO_PSP"
assert (df.loc[mask_issuer, "completed_at"].values >= issuer_ts[mask_issuer].values).all(), "FINAL_STATUS < ISSUER_RESPONSE"
assert (df.loc[mask_final, "completed_at"].values >= df.loc[mask_final, "initiated_at"].values).all(), "FINAL_STATUS < INITIATED"
assert (df.loc[mask_sent & mask_final, "completed_at"].values >= sent_ts[mask_sent & mask_final].values).all(), "FINAL_STATUS < SENT_TO_PSP"

# 5. every ISSUER_RESPONSE has a SENT_TO_PSP event
assert mask_issuer.sum() == (mask_issuer & mask_sent).sum(), "ISSUER_RESPONSE without SENT_TO_PSP"

# 6. FINAL_STATUS exists exactly when status is not PENDING
assert (mask_final == (df["status"] != "PENDING").values).all(), "FINAL_STATUS mismatch with non-PENDING"

# 7. INITIATED timestamp equals initiated_at
assert (ev_init["event_timestamp"].values == df["initiated_at"].values).all(), "INITIATED timestamp mismatch"

# 8. FINAL_STATUS timestamp equals completed_at
assert (ev_final["event_timestamp"].values == df.loc[mask_final, "completed_at"].values).all(), "FINAL_STATUS timestamp mismatch"

# 9. reconciliation has exactly one row per transaction (n rows)
assert len(df_recon) == n, f"Recon row count {len(df_recon)} != {n}"
assert df_recon["transaction_id"].is_unique, "Recon transaction_id not unique"

# 10. final_status in SUCCESS, FAILED, PENDING
assert df_recon["final_status"].isin(["SUCCESS", "FAILED", "PENDING"]).all(), "Invalid final_status"

# 11. settled_amount equals amount where final_status is SUCCESS and 0 otherwise
expected_amount = np.where(df_recon["final_status"] == "SUCCESS", df["amount"].values, 0.0)
assert np.isclose(df_recon["settled_amount"].values, expected_amount).all(), "settled_amount mismatch"

# 12. settlement_time is present exactly when final_status is SUCCESS
assert (df_recon["settlement_time"].notna() == (df_recon["final_status"] == "SUCCESS")).all(), "settlement_time presence mismatch"

# 13. settlement_time >= completed_at (or initiated_at for PENDING attempts)
succ_recon_mask = (df_recon["final_status"] == "SUCCESS").values
assert (settlement_time.loc[succ_recon_mask].values >= base_time_dt.values[succ_recon_mask]).all(), "settlement_time < base_time"

# 14. every settlement_time is earlier than EXTRACT_DATE
assert (settlement_time.loc[succ_recon_mask] < pd.Timestamp(EXTRACT_DATE)).all(), "settlement_time >= EXTRACT_DATE"

# 15. every row with was_debited True has mismatch_type "DEBITED_TIMEOUT"
assert (df_recon_truth.loc[df["was_debited"].values, "mismatch_type"] == "DEBITED_TIMEOUT").all(), "was_debited row without DEBITED_TIMEOUT"

# g. SAVE to data/raw/
events_export = events.copy()
events_export["event_timestamp"] = pd.to_datetime(events_export["event_timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S.%f")
events_export.to_csv(os.path.join(raw_dir, "payment_events.csv"), index=False)

recon_export = df_recon.copy()
recon_export["settled_amount"] = recon_export["settled_amount"].map(lambda x: f"{x:.2f}")
recon_export["settlement_time"] = pd.to_datetime(recon_export["settlement_time"]).dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
recon_export.to_csv(os.path.join(raw_dir, "reconciliation.csv"), index=False)

df_recon_truth.to_csv(os.path.join(raw_dir, "recon_truth.csv"), index=False)

# h. PRINT checks
print("=== 1. Event Counts & Counts by Type ===")
print(f"Total events:        {len(events):,}")
print(f"Events per attempt:  {len(events) / n:.2f}")
for ev_t, cnt in events["event_type"].value_counts().items():
    print(f"  {ev_t:<18} {cnt:>8,}")

print("\n=== 2. Event Patterns per Transaction ===")
patterns = pd.Series(
    "INITIATED"
    + np.where(mask_sent, ">SENT_TO_PSP", "")
    + np.where(mask_issuer, ">ISSUER_RESPONSE", "")
    + np.where(mask_final, ">FINAL_STATUS", "")
)
pat_counts = patterns.value_counts()
for pat, cnt in pat_counts.items():
    share = cnt / n * 100
    print(f"  {pat:<55} {cnt:>7,} ({share:>5.2f}%)")

print("\n=== 3. Top 8 Error Codes Among FAILED with No ISSUER_RESPONSE ===")
failed_no_issuer = df[(df["status"] == "FAILED") & (~mask_issuer)]
top8_codes = failed_no_issuer["error_code"].value_counts().head(8)
for code, cnt in top8_codes.items():
    print(f"  {code:<10} {cnt:>6,}")

print("\n=== 4. Latency Between Steps for SUCCESS Attempts ===")
is_succ_att = (df["status"] == "SUCCESS").values
init_to_sent_ms = (sent_ts[is_succ_att] - df.loc[is_succ_att, "initiated_at"]).dt.total_seconds() * 1000.0
issuer_to_final_ms = (df.loc[is_succ_att, "completed_at"] - issuer_ts[is_succ_att]).dt.total_seconds() * 1000.0
print(f"Median INITIATED to SENT_TO_PSP:        {np.median(init_to_sent_ms):.1f} ms")
print(f"Median ISSUER_RESPONSE to FINAL_STATUS: {np.median(issuer_to_final_ms):.1f} ms")

print("\n=== 5. Reconciliation Summary & Mismatch Breakdown ===")
print(f"Total reconciliation rows: {len(df_recon):,}")
print("Final status counts:")
for st, cnt in df_recon["final_status"].value_counts().items():
    print(f"  {st:<12} {cnt:>8,}")
print("Mismatch type counts:")
for mt, cnt in df_recon_truth["mismatch_type"].value_counts().items():
    print(f"  {mt:<26} {cnt:>8,}")

print("\n=== 6. Reconciliation Rate (Non-PENDING Attempts) ===")
non_pend_mask = (df["status"] != "PENDING").values
recon_matches = (df["status"].values[non_pend_mask] == final_status[non_pend_mask])
recon_rate = recon_matches.mean() * 100
mismatch_share = 100.0 - recon_rate
print(f"Reconciliation Rate: {recon_rate:.4f}%")
print(f"Mismatch Share:      {mismatch_share:.4f}%")

print("\n=== 7. Settlement Lag (Final SUCCESS, Attempt Non-PENDING) ===")
lag_mask = (final_status == "SUCCESS") & (df["status"] != "PENDING").values
comp_times = df.loc[lag_mask, "completed_at"].values
settle_times = settlement_time.values[lag_mask]
lag_h_actual = (pd.to_datetime(settle_times) - pd.to_datetime(comp_times)).total_seconds() / 3600.0
share_within_24h = (lag_h_actual <= 24.0).mean() * 100
med_lag_h = np.median(lag_h_actual)
max_lag_h = np.max(lag_h_actual)
print(f"Settled within 24h: {share_within_24h:.2f}%")
print(f"Median lag:         {med_lag_h:.2f} hours")
print(f"Max lag:            {max_lag_h:.2f} hours")

print("\n=== 8. Financial Reconciliation Impact ===")
succ_amt = df.loc[df["status"] == "SUCCESS", "amount"].sum()
settled_amt = df_recon["settled_amount"].sum()
deb_timeout_amt = df.loc[mismatch_type == "DEBITED_TIMEOUT", "amount"].sum()
reversal_amt = df.loc[mismatch_type == "RANDOM_REVERSAL", "amount"].sum()
print(f"Total SUCCESS amount:        Rs. {succ_amt:,.2f}")
print(f"Total settled amount:        Rs. {settled_amt:,.2f}")
print(f"DEBITED_TIMEOUT amount:      Rs. {deb_timeout_amt:,.2f}")
print(f"RANDOM_REVERSAL amount:      Rs. {reversal_amt:,.2f}")

print("\n=== 9. Double Charge Visibility ===")
intent_ids = df["intent_id"].values
recon_succ_mask = (final_status == "SUCCESS")
recon_succ_intents = pd.Series(intent_ids[recon_succ_mask]).value_counts()
multi_succ_intents = set(recon_succ_intents[recon_succ_intents >= 2].index)

dup_debit_intents = set(df_txn_truth.loc[df_txn_truth["is_duplicate_debit"] == True, "intent_id"])
total_dup_debit = (df_txn_truth["is_duplicate_debit"] == True).sum()

overlap = multi_succ_intents.intersection(dup_debit_intents)
print(f"Intents with >= 2 settled successes:               {len(multi_succ_intents):,}")
print(f"Of which have is_duplicate_debit True:             {len(overlap):,}")
print(f"Total is_duplicate_debit rows in transaction_truth: {total_dup_debit:,}")

print("\nEvents and reconciliation generated OK")
