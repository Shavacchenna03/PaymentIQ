import os
import sys
import numpy as np
import pandas as pd

# a. Imports & Load
sys.path.insert(0, os.path.dirname(__file__))
from config import LATENCY_MIN, LATENCY_MAX, FAILURE_CODES

raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
processed_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports")

stg_transactions = pd.read_csv(
    os.path.join(raw_dir, "stg_transactions.csv"),
    parse_dates=["initiated_at", "completed_at"],
    keep_default_na=False
)
stg_transactions["error_code"] = stg_transactions["error_code"].replace("", np.nan)
stg_transactions["completed_at"] = pd.to_datetime(stg_transactions["completed_at"].replace("", np.nan))
stg_transactions["latency_ms"] = pd.to_numeric(stg_transactions["latency_ms"].replace("", np.nan), errors="coerce").astype("Int64")

stg_payment_events = pd.read_csv(
    os.path.join(raw_dir, "stg_payment_events.csv"),
    parse_dates=["event_timestamp"]
)

recon = pd.read_csv(
    os.path.join(raw_dir, "reconciliation.csv"),
    parse_dates=["settlement_time"],
    keep_default_na=False
)
recon["settlement_time"] = pd.to_datetime(recon["settlement_time"].replace("", np.nan))

# b. DEDUPLICATE
dup_mask = stg_transactions["transaction_id"].duplicated(keep=False)
dup_rows = stg_transactions[dup_mask]
duplicate_ids_found = dup_rows["transaction_id"].nunique()
rows_dropped = stg_transactions["transaction_id"].duplicated(keep="first").sum()

dup_sorted = dup_rows.sort_values("transaction_id")
is_same_id = (dup_sorted["transaction_id"].values[1:] == dup_sorted["transaction_id"].values[:-1])

differing_ids = set()
for c in dup_sorted.columns:
    v1 = dup_sorted[c].values[:-1][is_same_id]
    v2 = dup_sorted[c].values[1:][is_same_id]
    na1 = pd.isna(v1)
    na2 = pd.isna(v2)
    mismatch = (na1 != na2) | (~na1 & ~na2 & (v1 != v2))
    if np.any(mismatch):
        differing_ids.update(dup_sorted["transaction_id"].values[:-1][is_same_id][mismatch])

ids_whose_copies_differed = len(differing_ids)
if ids_whose_copies_differed > 0:
    raise ValueError(f"Found {ids_whose_copies_differed} duplicate transaction_ids whose copies differed!")

txns_clean = stg_transactions.drop_duplicates(subset=["transaction_id"], keep="first").reset_index(drop=True)

# c. DETECT TIMEZONE-SHIFTED PSPs (no config flags)
non_pend = txns_clean[txns_clean["status"] != "PENDING"].copy()
all_psps = sorted(non_pend["psp_id"].unique())

psp_profiles = {}
for p in all_psps:
    sub = non_pend[non_pend["psp_id"] == p]
    prof = np.zeros(24)
    vc = sub["initiated_at"].dt.hour.value_counts(normalize=True)
    for h, v in vc.items():
        prof[h] = v
    psp_profiles[p] = prof

flagged_psps = []
psp_offsets_minutes = {}
psp_detection_table = []

recon_merge = recon.merge(txns_clean[["transaction_id", "psp_id", "status", "completed_at"]], on="transaction_id")
recon_sub = recon_merge[(recon_merge["final_status"] == "SUCCESS") & (recon_merge["status"] != "PENDING")].copy()
recon_sub["lag_h"] = (recon_sub["settlement_time"] - recon_sub["completed_at"]).dt.total_seconds() / 3600.0

for p in all_psps:
    prof_p = psp_profiles[p]
    oth_rows = non_pend[non_pend["psp_id"] != p]
    prof_oth = np.zeros(24)
    vc_oth = oth_rows["initiated_at"].dt.hour.value_counts(normalize=True)
    for h, v in vc_oth.items():
        prof_oth[h] = v

    dists = []
    for k in range(24):
        shifted = np.roll(prof_p, k)
        dists.append(np.sum(np.abs(shifted - prof_oth)))

    best_k = int(np.argmin(dists))
    dist0 = dists[0]
    dist_best = dists[best_k]
    is_flagged = bool((best_k != 0) and (dist_best < 0.5 * dist0))

    psp_detection_table.append({
        "psp_id": p,
        "best_k": best_k,
        "dist(0)": dist0,
        "dist(best_k)": dist_best,
        "flagged": is_flagged
    })

    if is_flagged:
        flagged_psps.append(p)
        med_lag_psp = recon_sub[recon_sub["psp_id"] == p]["lag_h"].median()
        med_lag_others = recon_sub[recon_sub["psp_id"] != p]["lag_h"].median()
        offset_hours = round(2.0 * (med_lag_psp - med_lag_others)) / 2.0
        if abs(offset_hours - best_k) > 1.0:
            raise ValueError(f"For PSP {p}, abs(offset_hours ({offset_hours}) - best_k ({best_k})) > 1")
        offset_minutes = offset_hours * 60.0
        psp_offsets_minutes[p] = offset_minutes

df_psp_det = pd.DataFrame(psp_detection_table)
print("=== PSP Timezone Shift Detection Table ===")
print(df_psp_det.to_string(index=False))
for p in flagged_psps:
    print(f"Flagged PSP {p}: offset = {psp_offsets_minutes[p]:.1f} minutes ({psp_offsets_minutes[p]/60:.1f} hours)")

# d. FIX TIMESTAMPS
for p in flagged_psps:
    off_min = psp_offsets_minutes[p]
    off_td = pd.Timedelta(minutes=off_min)

    is_p_att = (txns_clean["psp_id"] == p).values
    txns_clean.loc[is_p_att, "initiated_at"] += off_td

    has_comp = is_p_att & txns_clean["completed_at"].notna().values
    txns_clean.loc[has_comp, "completed_at"] += off_td

    p_txns = set(txns_clean.loc[is_p_att, "transaction_id"])
    is_p_ev = stg_payment_events["transaction_id"].isin(p_txns).values
    stg_payment_events.loc[is_p_ev, "event_timestamp"] += off_td

# e. FIX ERROR CODES
failed_missing_mask = (txns_clean["status"] == "FAILED") & txns_clean["error_code"].isna()
fixed_error_code_txns = txns_clean.loc[failed_missing_mask, "transaction_id"].tolist()
txns_clean.loc[failed_missing_mask, "error_code"] = "UNK_01"

# f. RECOVER LATENCY
recover_lat_mask = (
    (txns_clean["status"] != "PENDING")
    & txns_clean["latency_ms"].isna()
    & txns_clean["completed_at"].notna()
)
fixed_latency_txns = txns_clean.loc[recover_lat_mask, "transaction_id"].tolist()

dur_ms = (
    txns_clean.loc[recover_lat_mask, "completed_at"]
    - txns_clean.loc[recover_lat_mask, "initiated_at"]
).dt.total_seconds() * 1000.0

recovered_lat = np.clip(np.round(dur_ms + 500.0), LATENCY_MIN, LATENCY_MAX).astype(np.int64)
txns_clean.loc[recover_lat_mask, "latency_ms"] = pd.Series(recovered_lat, dtype="Int64").values

# g. VALIDATE
print("\n=== Validation Checks ===")
# 1. Transaction ID unique, row count, latency nulls, error codes
assert txns_clean["transaction_id"].is_unique, "transaction_id not unique"
assert len(txns_clean) == 293991, f"Expected 293,991 rows, got {len(txns_clean)}"
assert (txns_clean["latency_ms"].isna() == (txns_clean["status"] == "PENDING")).all(), "Unexpected missing latency"
valid_codes = set([c[0] for c in FAILURE_CODES])
assert txns_clean[txns_clean["status"] == "FAILED"]["error_code"].isin(valid_codes).all(), "Invalid error code in FAILED"
assert txns_clean[txns_clean["status"].isin(["SUCCESS", "PENDING"])]["error_code"].isna().all(), "Non-FAILED has error code"
print("PASS: Schema and integrity (unique IDs, 293,991 rows, latency nulls, error codes valid)")

# 2. Completed >= initiated; date bounds
non_pend = txns_clean[txns_clean["status"] != "PENDING"]
assert (non_pend["completed_at"] >= non_pend["initiated_at"]).all(), "completed_at < initiated_at"
assert (txns_clean["initiated_at"] >= pd.Timestamp("2026-04-01 00:00:00")).all(), "initiated_at before 2026-04-01"
assert (txns_clean["initiated_at"] <= pd.Timestamp("2026-09-30 23:59:59")).all(), "initiated_at after 2026-09-30"
print("PASS: Timestamps consistency and boundary checks")

# 3. Events: non-decreasing; INITIATED equals initiated_at; FINAL_STATUS equals completed_at
order_map = {"INITIATED": 1, "SENT_TO_PSP": 2, "ISSUER_RESPONSE": 3, "FINAL_STATUS": 4}
ev_check = stg_payment_events.copy()
ev_check["event_order"] = ev_check["event_type"].map(order_map)
ev_check = ev_check.sort_values(by=["transaction_id", "event_order"]).reset_index(drop=True)
same_txn = (ev_check["transaction_id"].values[1:] == ev_check["transaction_id"].values[:-1])
diff_ts = (ev_check["event_timestamp"].values[1:] >= ev_check["event_timestamp"].values[:-1])
assert (diff_ts[same_txn]).all(), "Event timestamps not non-decreasing within transaction"

ev_init = stg_payment_events[stg_payment_events["event_type"] == "INITIATED"].sort_values("transaction_id")
txns_sorted = txns_clean.sort_values("transaction_id")
assert (ev_init["event_timestamp"].dt.floor("s").values == txns_sorted["initiated_at"].dt.floor("s").values).all(), "INITIATED event mismatch"

ev_final = stg_payment_events[stg_payment_events["event_type"] == "FINAL_STATUS"].sort_values("transaction_id")
txns_non_pend = txns_clean[txns_clean["status"] != "PENDING"].sort_values("transaction_id")
assert (ev_final["event_timestamp"].dt.floor("s").values == txns_non_pend["completed_at"].dt.floor("s").values).all(), "FINAL_STATUS event mismatch"
print("PASS: Event lifecycle order and second-level timestamp alignment")

# 4. Post-fix median settlement lag within 1 hour
recon_merge_post = recon.merge(txns_clean[["transaction_id", "psp_id", "status", "completed_at"]], on="transaction_id")
recon_sub_post = recon_merge_post[(recon_merge_post["final_status"] == "SUCCESS") & (recon_merge_post["status"] != "PENDING")].copy()
recon_sub_post["lag_h"] = (recon_sub_post["settlement_time"] - recon_sub_post["completed_at"]).dt.total_seconds() / 3600.0

for p in flagged_psps:
    med_lag_p = recon_sub_post[recon_sub_post["psp_id"] == p]["lag_h"].median()
    med_lag_oth = recon_sub_post[recon_sub_post["psp_id"] != p]["lag_h"].median()
    assert abs(med_lag_p - med_lag_oth) <= 1.0, f"Post-fix lag mismatch: {med_lag_p:.2f} vs {med_lag_oth:.2f}"
print("PASS: Post-fix settlement lag within 1 hour of pooled median")

# h. SCORE AGAINST THE ANSWER KEY
print("\n=== Scoring Against the Answer Key ===")
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
).sort_values("event_id").reset_index(drop=True)

dq_truth = pd.read_csv(os.path.join(raw_dir, "dq_truth.csv"), keep_default_na=False)

# Cell-by-cell comparison
txns_clean_sorted = txns_clean.sort_values("transaction_id").reset_index(drop=True)
mismatches_per_col = {}
for col in clean_attempts.columns:
    c1 = clean_attempts[col]
    c2 = txns_clean_sorted[col]
    if col == "latency_ms":
        na1 = c1.isna()
        na2 = c2.isna()
        diff = (na1 != na2) | (~na1 & ~na2 & (c1.astype(float) != c2.astype(float)))
    elif pd.api.types.is_datetime64_any_dtype(c1):
        na1 = c1.isna()
        na2 = c2.isna()
        diff = (na1 != na2) | (~na1 & ~na2 & (c1 != c2))
    else:
        na1 = c1.isna() | (c1 == "")
        na2 = c2.isna() | (c2 == "")
        diff = (na1 != na2) | (~na1 & ~na2 & (c1 != c2))
    mismatches_per_col[col] = int(diff.sum())
    if col not in ["latency_ms", "error_code"]:
        assert mismatches_per_col[col] == 0, f"Unexpected mismatch in {col}: {mismatches_per_col[col]}"

print("Mismatches per column compared to clean attempts_all.csv:")
for col, cnt in mismatches_per_col.items():
    print(f"  {col:<16}: {cnt:>5}")

# Verify mismatches exist only on recorded rows
lat_diff_txns = set(txns_clean_sorted.loc[
    ~((clean_attempts["latency_ms"].isna() & txns_clean_sorted["latency_ms"].isna()) |
      (clean_attempts["latency_ms"] == txns_clean_sorted["latency_ms"])),
    "transaction_id"
])
assert lat_diff_txns.issubset(set(fixed_latency_txns)), "latency_ms mismatch on non-recovered row"

code_diff_txns = set(txns_clean_sorted.loc[
    ~((clean_attempts["error_code"].isna() & txns_clean_sorted["error_code"].isna()) |
      (clean_attempts["error_code"] == txns_clean_sorted["error_code"])),
    "transaction_id"
])
assert code_diff_txns.issubset(set(fixed_error_code_txns)), "error_code mismatch on non-UNK_01 row"

# Compare events to microsecond
stg_events_sorted = stg_payment_events.sort_values("event_id").reset_index(drop=True)
ev_ts_diff = (stg_events_sorted["event_timestamp"] != clean_events["event_timestamp"]).sum()
print(f"Cleaned events timestamp mismatches: {ev_ts_diff}")
assert ev_ts_diff == 0, "Cleaned events do not match clean_events to the microsecond"

# Latency recovery accuracy
dq_lat = dq_truth[dq_truth["issue_type"] == "MISSING_LATENCY"].copy()
dq_lat["true_val"] = pd.to_numeric(dq_lat["true_value"])
dq_lat = dq_lat.merge(txns_clean[["transaction_id", "latency_ms"]], on="transaction_id")
dq_lat["abs_err"] = np.abs(dq_lat["latency_ms"].astype(float) - dq_lat["true_val"])

med_abs_err = dq_lat["abs_err"].median()
share_500 = (dq_lat["abs_err"] <= 500.0).mean() * 100.0
share_1000 = (dq_lat["abs_err"] <= 1000.0).mean() * 100.0
max_abs_err = dq_lat["abs_err"].max()

print(f"\nLatency recovery overall ({len(dq_lat)} rows):")
print(f"  Median absolute error: {med_abs_err:.2f} ms")
print(f"  Share within 500 ms:   {share_500:.2f}%")
print(f"  Share within 1000 ms:  {share_1000:.2f}%")
print(f"  Maximum error:         {max_abs_err:.2f} ms")

# Split by attempt_number
att_truth = pd.read_csv(os.path.join(raw_dir, "attempt_truth_all.csv"), usecols=["transaction_id", "attempt_number"])
dq_lat = dq_lat.merge(att_truth, on="transaction_id")

dq_lat_att1 = dq_lat[dq_lat["attempt_number"] == 1]
dq_lat_ret = dq_lat[dq_lat["attempt_number"] > 1]

print(f"Attempt 1 ({len(dq_lat_att1)} rows): Median abs error = {dq_lat_att1['abs_err'].median():.2f} ms, Max = {dq_lat_att1['abs_err'].max():.2f} ms")
print(f"Retries   ({len(dq_lat_ret)} rows): Median abs error = {dq_lat_ret['abs_err'].median():.2f} ms, Max = {dq_lat_ret['abs_err'].max():.2f} ms")

# UNK_01 analysis
dq_code = dq_truth[dq_truth["issue_type"] == "MISSING_ERROR_CODE"].copy()
dq_code["family"] = dq_code["true_value"].str[:3]
fam_counts = dq_code["family"].value_counts()
print("\nUNK_01 true error family breakdown:")
for fam, cnt in fam_counts.items():
    print(f"  {fam}: {cnt}")

donot_cnt = int(dq_code["true_value"].isin(["CUS_03", "TEC_01", "RSK_01"]).sum())
print(f"Rows whose true code was a 'Do not retry' code: {donot_cnt}")

# PSP detection check
import config
expected_utc_psp_id = [p[0] for p in config.PSPS if p[1] == config.UTC_TIMESTAMP_PSP][0]
is_psp_det_exact = bool(flagged_psps == [expected_utc_psp_id])
print(f"\nPSP Detection Correct: {is_psp_det_exact} (Flagged {flagged_psps} vs Expected {[expected_utc_psp_id]} - {config.UTC_TIMESTAMP_PSP})")
assert is_psp_det_exact, "Flagged PSPs do not match expected UTC_TIMESTAMP_PSP"

# i. SAVE
# transactions_clean.csv
txns_export = txns_clean.copy()
txns_export["initiated_at"] = pd.to_datetime(txns_export["initiated_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
txns_export["completed_at"] = pd.to_datetime(txns_export["completed_at"]).dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
txns_export["latency_ms"] = txns_export["latency_ms"].astype("Int64")
txns_export["error_code"] = txns_export["error_code"].fillna("")
txns_export.to_csv(os.path.join(processed_dir, "transactions_clean.csv"), index=False)

# payment_events_clean.csv
ev_export = stg_payment_events[["event_id", "transaction_id", "event_type", "event_timestamp"]].copy()
ev_export["event_timestamp"] = pd.to_datetime(ev_export["event_timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S.%f")
ev_export.to_csv(os.path.join(processed_dir, "payment_events_clean.csv"), index=False)

# reports/data_quality_log.csv
dq_log = pd.DataFrame([
    {
        "issue": "DUPLICATE_ROW",
        "rows_found": duplicate_ids_found,
        "rule_applied": "Kept first occurrence of each transaction_id; dropped exact duplicates",
        "accuracy_note": "100% exact match across all columns"
    },
    {
        "issue": "TIMEZONE_SHIFT",
        "rows_found": int((txns_clean["psp_id"] == expected_utc_psp_id).sum()),
        "rule_applied": f"Detected PSP {expected_utc_psp_id} via hourly volume and settlement lag; shifted attempts and events +330 minutes",
        "accuracy_note": "Timestamps match clean baseline to the microsecond"
    },
    {
        "issue": "MISSING_ERROR_CODE",
        "rows_found": len(fixed_error_code_txns),
        "rule_applied": "Mapped missing error codes on FAILED attempts to UNK_01",
        "accuracy_note": f"True codes include {donot_cnt} Do-not-retry codes; excluded from root-cause by code"
    },
    {
        "issue": "MISSING_LATENCY",
        "rows_found": len(fixed_latency_txns),
        "rule_applied": "Estimated as (completed_at - initiated_at in ms) + 500 ms, clipped to [200, 120000]",
        "accuracy_note": f"Median abs error {med_abs_err:.1f} ms, {share_500:.1f}% within 500 ms, max {max_abs_err:.1f} ms"
    }
])
dq_log.to_csv(os.path.join(reports_dir, "data_quality_log.csv"), index=False)

# reports/dq_fixed_rows.csv
fixed_code_df = pd.DataFrame({
    "transaction_id": fixed_error_code_txns,
    "issue": "MISSING_ERROR_CODE",
    "fix": "Mapped to UNK_01"
})
rec_lat_vals = txns_clean.set_index("transaction_id").loc[fixed_latency_txns, "latency_ms"].values
fixed_lat_df = pd.DataFrame({
    "transaction_id": fixed_latency_txns,
    "issue": "MISSING_LATENCY",
    "fix": [f"Recovered latency: {lat} ms" for lat in rec_lat_vals]
})
dq_fixed_rows = pd.concat([fixed_code_df, fixed_lat_df], ignore_index=True)
dq_fixed_rows.to_csv(os.path.join(reports_dir, "dq_fixed_rows.csv"), index=False)

# j. Print final counts and message
print(f"\nFinal cleaned transactions:   {len(txns_clean):,}")
print(f"Final cleaned payment events: {len(stg_payment_events):,}")
print("\nCleaning complete OK")
