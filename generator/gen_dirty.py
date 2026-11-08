import os
import sys
import numpy as np
import pandas as pd

# a. Imports & RNG
sys.path.insert(0, os.path.dirname(__file__))
from config import *

rng = np.random.default_rng(SEED + 6)

# b. LOAD CSVs
raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

clean_attempts = pd.read_csv(
    os.path.join(raw_dir, "attempts_all.csv"),
    parse_dates=["initiated_at", "completed_at"],
    keep_default_na=False
)
clean_attempts["error_code"] = clean_attempts["error_code"].replace("", np.nan)
clean_attempts["completed_at"] = pd.to_datetime(clean_attempts["completed_at"].replace("", np.nan))
clean_attempts["latency_ms"] = pd.to_numeric(clean_attempts["latency_ms"].replace("", np.nan), errors="coerce").astype("Int64")
clean_attempts = clean_attempts.sort_values("transaction_id").reset_index(drop=True)

clean_events = pd.read_csv(
    os.path.join(raw_dir, "payment_events.csv"),
    parse_dates=["event_timestamp"]
)
clean_events = clean_events.sort_values("event_id").reset_index(drop=True)

clean_recon = pd.read_csv(
    os.path.join(raw_dir, "reconciliation.csv"),
    parse_dates=["settlement_time"],
    keep_default_na=False
)
clean_recon["settlement_time"] = pd.to_datetime(clean_recon["settlement_time"].replace("", np.nan))
clean_recon = clean_recon.sort_values("transaction_id").reset_index(drop=True)

stg = clean_attempts.copy()
stg_events = clean_events.copy()

# c. Draw issues in exact order
# 1. MISSING_LATENCY
elig1_mask = (stg["status"] != "PENDING") & stg["latency_ms"].notna()
elig1_indices = np.where(elig1_mask)[0]
n1 = int(round(MISSING_LATENCY_RATE * len(elig1_indices)))

idx1 = rng.choice(elig1_indices, size=n1, replace=False)
dq_latency_txns = stg.loc[idx1, "transaction_id"].values
dq_latency_trues = stg.loc[idx1, "latency_ms"].astype(str).values
stg.loc[idx1, "latency_ms"] = pd.NA

# 2. MISSING_ERROR_CODE
elig2_mask = (stg["status"] == "FAILED")
elig2_indices = np.where(elig2_mask)[0]
n2 = int(round(MISSING_CODE_RATE * len(elig2_indices)))

idx2 = rng.choice(elig2_indices, size=n2, replace=False)
dq_code_txns = stg.loc[idx2, "transaction_id"].values
dq_code_trues = stg.loc[idx2, "error_code"].values
stg.loc[idx2, "error_code"] = np.nan

# 3. UTC_TIMESTAMPS
quickrail_psp_id = [p[0] for p in PSPS if p[1] == UTC_TIMESTAMP_PSP][0]
offset_delta = pd.Timedelta(minutes=UTC_OFFSET_MINUTES)

is_qr_attempt = (stg["psp_id"] == quickrail_psp_id).values
stg.loc[is_qr_attempt, "initiated_at"] = stg.loc[is_qr_attempt, "initiated_at"] - offset_delta

qr_has_comp = is_qr_attempt & stg["completed_at"].notna().values
stg.loc[qr_has_comp, "completed_at"] = stg.loc[qr_has_comp, "completed_at"] - offset_delta

qr_txns = set(stg.loc[is_qr_attempt, "transaction_id"])
is_qr_event = stg_events["transaction_id"].isin(qr_txns).values
stg_events.loc[is_qr_event, "event_timestamp"] = stg_events.loc[is_qr_event, "event_timestamp"] - offset_delta

# 4. DUPLICATE_ROW
n_before_dup = len(stg)
n4 = int(round(DUPLICATE_ROW_RATE * n_before_dup))
idx4 = rng.choice(n_before_dup, size=n4, replace=False)

dup_rows = stg.iloc[idx4].copy()
dq_dup_txns = dup_rows["transaction_id"].values
stg = pd.concat([stg, dup_rows], ignore_index=True)

# d. ASSERTS
# 1. Row counts
assert len(stg) == len(clean_attempts) + n4, f"stg row count mismatch: {len(stg)} != {len(clean_attempts) + n4}"
assert len(stg_events) == len(clean_events), f"stg_events row count mismatch: {len(stg_events)} != {len(clean_events)}"

# 2. Duplicate rows are exact copies
appended_rows = stg.iloc[-n4:].reset_index(drop=True)
original_chosen_rows = stg.iloc[idx4].reset_index(drop=True)
assert appended_rows.equals(original_chosen_rows), "Appended duplicate rows mismatch chosen rows"

dup_txns_found = stg[stg["transaction_id"].duplicated(keep=False)]["transaction_id"].unique()
assert len(dup_txns_found) == n4, f"Duplicate transaction count mismatch: {len(dup_txns_found)} != {n4}"
assert set(dup_txns_found) == set(dq_dup_txns), "Duplicate transaction IDs mismatch"

# 3. Missing values on first len(clean_attempts) rows
stg_first = stg.iloc[:len(clean_attempts)]
assert clean_attempts.loc[idx1, "completed_at"].notna().all(), "MISSING_LATENCY row had missing completed_at"
assert (clean_attempts.loc[idx1, "status"] != "PENDING").all(), "MISSING_LATENCY row was PENDING"
assert (clean_attempts.loc[idx2, "status"] == "FAILED").all(), "MISSING_ERROR_CODE row was not FAILED"

expected_missing_lat = (clean_attempts["status"] == "PENDING") | clean_attempts.index.isin(idx1)
assert (stg_first["latency_ms"].isna().values == expected_missing_lat.values).all(), "latency_ms missing on unexpected rows"

expected_missing_code = clean_attempts["status"].isin(["SUCCESS", "PENDING"]) | clean_attempts.index.isin(idx2)
assert (stg_first["error_code"].isna().values == expected_missing_code.values).all(), "error_code missing on unexpected rows"

# 4. QuickRail timestamps shifted by exactly 330 minutes; other PSPs identical
qr_init_clean = clean_attempts.loc[is_qr_attempt, "initiated_at"]
qr_init_stg = stg_first.loc[is_qr_attempt, "initiated_at"]
assert (qr_init_stg.values == (qr_init_clean - offset_delta).values).all(), "QuickRail initiated_at not shifted by 330m"

qr_comp_clean = clean_attempts.loc[qr_has_comp, "completed_at"]
qr_comp_stg = stg_first.loc[qr_has_comp, "completed_at"]
assert (qr_comp_stg.values == (qr_comp_clean - offset_delta).values).all(), "QuickRail completed_at not shifted by 330m"

other_init_clean = clean_attempts.loc[~is_qr_attempt, "initiated_at"]
other_init_stg = stg_first.loc[~is_qr_attempt, "initiated_at"]
assert (other_init_stg.values == other_init_clean.values).all(), "Non-QuickRail initiated_at altered"

other_has_comp = (~is_qr_attempt) & clean_attempts["completed_at"].notna().values
other_comp_clean = clean_attempts.loc[other_has_comp, "completed_at"]
other_comp_stg = stg_first.loc[other_has_comp, "completed_at"]
assert (other_comp_stg.values == other_comp_clean.values).all(), "Non-QuickRail completed_at altered"

# 5. QuickRail events shifted by 330 minutes; other events identical; non-decreasing
assert (stg_events.loc[is_qr_event, "event_timestamp"].values == (clean_events.loc[is_qr_event, "event_timestamp"] - offset_delta).values).all(), "QuickRail events not shifted by 330m"
assert (stg_events.loc[~is_qr_event, "event_timestamp"].values == clean_events.loc[~is_qr_event, "event_timestamp"].values).all(), "Non-QuickRail events altered"

order_map = {"INITIATED": 1, "SENT_TO_PSP": 2, "ISSUER_RESPONSE": 3, "FINAL_STATUS": 4}
ev_check = stg_events.copy()
ev_check["event_order"] = ev_check["event_type"].map(order_map)
ev_check = ev_check.sort_values(by=["transaction_id", "event_order"]).reset_index(drop=True)
same_txn = (ev_check["transaction_id"].values[1:] == ev_check["transaction_id"].values[:-1])
diff_ts = (ev_check["event_timestamp"].values[1:] >= ev_check["event_timestamp"].values[:-1])
assert (diff_ts[same_txn]).all(), "Event timestamps not non-decreasing within transaction"

# 6. Unchanged columns identical
unchanged_cols = [
    "transaction_id", "customer_id", "payee_id", "payee_category", "bank_id",
    "psp_id", "amount", "status", "device_type", "network_type", "channel"
]
assert stg_first[unchanged_cols].equals(clean_attempts[unchanged_cols]), "Unchanged columns differ in stg_transactions"
assert stg_events[["event_id", "transaction_id", "event_type"]].equals(clean_events[["event_id", "transaction_id", "event_type"]]), "Metadata differs in stg_payment_events"

# e. SAVE to data/raw/
stg_export = stg.copy()
stg_export["initiated_at"] = pd.to_datetime(stg_export["initiated_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
stg_export["completed_at"] = pd.to_datetime(stg_export["completed_at"]).dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
stg_export["latency_ms"] = stg_export["latency_ms"].astype("Int64")
stg_export["error_code"] = stg_export["error_code"].fillna("")
stg_export.to_csv(os.path.join(raw_dir, "stg_transactions.csv"), index=False)

events_export = stg_events.copy()
events_export["event_timestamp"] = pd.to_datetime(events_export["event_timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S.%f")
events_export.to_csv(os.path.join(raw_dir, "stg_payment_events.csv"), index=False)

# dq_truth.csv
df_dq_lat = pd.DataFrame({
    "transaction_id": dq_latency_txns,
    "issue_type": "MISSING_LATENCY",
    "true_value": dq_latency_trues
})
df_dq_code = pd.DataFrame({
    "transaction_id": dq_code_txns,
    "issue_type": "MISSING_ERROR_CODE",
    "true_value": dq_code_trues
})
df_dq_dup = pd.DataFrame({
    "transaction_id": dq_dup_txns,
    "issue_type": "DUPLICATE_ROW",
    "true_value": ""
})
df_dq_truth = pd.concat([df_dq_lat, df_dq_code, df_dq_dup], ignore_index=True)
df_dq_truth.to_csv(os.path.join(raw_dir, "dq_truth.csv"), index=False)

# dq_planted_summary.csv
df_planted = pd.DataFrame({
    "issue_type": ["MISSING_LATENCY", "MISSING_ERROR_CODE", "UTC_TIMESTAMPS", "DUPLICATE_ROW"],
    "rows_affected": [n1, n2, int(is_qr_attempt.sum()), n4],
    "description": [
        "0.2 percent of non-PENDING rows with latency_ms blanked",
        "0.3 percent of FAILED rows with error_code blanked",
        "QuickRail writes UTC (5 hours 30 minutes behind IST)",
        "0.1 percent of rows duplicated exactly"
    ]
})
df_planted.to_csv(os.path.join(raw_dir, "dq_planted_summary.csv"), index=False)

# f. PRINT checks
print("=== 1. Staging Counts & Issues Planted ===")
print(f"Clean attempts:              {len(clean_attempts):,}")
print(f"Staging transactions:        {len(stg):,} (added {n4:,} duplicates)")
print(f"Staging payment events:      {len(stg_events):,}")
print(f"MISSING_LATENCY rows (n1):   {n1:,}")
print(f"MISSING_ERROR_CODE rows (n2):{n2:,}")
print(f"DUPLICATE_ROW rows (n4):     {n4:,}")
print(f"QuickRail attempts shifted:  {is_qr_attempt.sum():,}")
print(f"QuickRail events shifted:    {is_qr_event.sum():,}")

print("\n=== 2. Planted Data Quality Summary ===")
print(df_planted.to_string(index=False))

print("\n=== 3. DETECTION SIGNAL 1: Hourly Distribution (Hours 20-21) ===")
# Use non-PENDING rows from first occurrence of each transaction
stg_non_pend = stg_first[stg_first["status"] != "PENDING"].copy()
clean_non_pend = clean_attempts[clean_attempts["status"] != "PENDING"].copy()

qr_stg = stg_non_pend[stg_non_pend["psp_id"] == quickrail_psp_id]
other_stg = stg_non_pend[stg_non_pend["psp_id"] != quickrail_psp_id]

qr_clean = clean_non_pend[clean_non_pend["psp_id"] == quickrail_psp_id]
other_clean = clean_non_pend[clean_non_pend["psp_id"] != quickrail_psp_id]

def hour_stats(df_sub):
    h = df_sub["initiated_at"].dt.hour
    share_20_21 = (h.isin([20, 21])).mean() * 100
    vc = h.value_counts(normalize=True) * 100
    peak_h = vc.idxmax()
    peak_share = vc.max()
    return share_20_21, peak_h, peak_share

s20_qr_stg, pk_qr_stg, pks_qr_stg = hour_stats(qr_stg)
s20_oth_stg, pk_oth_stg, pks_oth_stg = hour_stats(other_stg)
s20_qr_cln, pk_qr_cln, pks_qr_cln = hour_stats(qr_clean)
s20_oth_cln, pk_oth_cln, pks_oth_cln = hour_stats(other_clean)

print(f"Staging QuickRail:      Hours 20-21 = {s20_qr_stg:>5.2f}%, Peak Hour = {pk_qr_stg:>2}:00 ({pks_qr_stg:.2f}%)")
print(f"Staging Other PSPs:     Hours 20-21 = {s20_oth_stg:>5.2f}%, Peak Hour = {pk_oth_stg:>2}:00 ({pks_oth_stg:.2f}%)")
print(f"Clean QuickRail:        Hours 20-21 = {s20_qr_cln:>5.2f}%, Peak Hour = {pk_qr_cln:>2}:00 ({pks_qr_cln:.2f}%)")
print(f"Clean Other PSPs:       Hours 20-21 = {s20_oth_cln:>5.2f}%, Peak Hour = {pk_oth_cln:>2}:00 ({pks_oth_cln:.2f}%)")

print("\n=== 4. DETECTION SIGNAL 2: Settlement Lag vs Bank Recon ===")
# Merge clean_recon with stg_first
recon_merge = clean_recon.merge(stg_first[["transaction_id", "psp_id", "status", "completed_at"]], on="transaction_id")
recon_sub = recon_merge[(recon_merge["final_status"] == "SUCCESS") & (recon_merge["status"] != "PENDING")].copy()

recon_sub["lag_h"] = (recon_sub["settlement_time"] - recon_sub["completed_at"]).dt.total_seconds() / 3600.0

qr_recon = recon_sub[recon_sub["psp_id"] == quickrail_psp_id]
other_recon = recon_sub[recon_sub["psp_id"] != quickrail_psp_id]

qr_med_lag = qr_recon["lag_h"].median()
qr_within_24 = (qr_recon["lag_h"] <= 24.0).mean() * 100

other_med_lag = other_recon["lag_h"].median()
other_within_24 = (other_recon["lag_h"] <= 24.0).mean() * 100

print(f"QuickRail (Staging vs Recon):  Median Lag = {qr_med_lag:>5.2f} h, Settled within 24h = {qr_within_24:>5.2f}%")
print(f"Other PSPs (Staging vs Recon): Median Lag = {other_med_lag:>5.2f} h, Settled within 24h = {other_within_24:>5.2f}%")

print("\n=== 5. Early Boundary Rows (QuickRail Before 2026-04-01 00:00) ===")
qr_early_cnt = (qr_stg["initiated_at"] < pd.Timestamp("2026-04-01 00:00:00")).sum()
print(f"QuickRail attempts shifted before 2026-04-01 00:00: {qr_early_cnt:,}")

print("\n=== 6. Latency Recovery Accuracy for MISSING_LATENCY Rows ===")
true_lats = clean_attempts.loc[idx1, "latency_ms"].astype(float).values
stg_comp_idx1 = stg_first.loc[idx1, "completed_at"]
stg_init_idx1 = stg_first.loc[idx1, "initiated_at"]
approx_lats = (stg_comp_idx1 - stg_init_idx1).dt.total_seconds() * 1000.0 + 500.0
abs_diffs = np.abs(true_lats - approx_lats.values)

print(f"Median absolute error: {np.median(abs_diffs):.2f} ms")
print(f"Max absolute error:    {np.max(abs_diffs):.2f} ms")

print("\n=== 7. FAILED Rows Missing Error Code ===")
failed_missing_codes = (stg_first["status"] == "FAILED") & stg_first["error_code"].isna()
print(f"FAILED rows with missing error_code: {failed_missing_codes.sum():,} (must equal n2 = {n2:,})")
assert failed_missing_codes.sum() == n2, "Mismatch in missing error code count"

print("\nDirty staging data generated OK")
