import os
import sys
from datetime import date
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# a. Imports & RNG
sys.path.insert(0, os.path.dirname(__file__))
from config import *

rng = np.random.default_rng(SEED + 4)

# b. LOAD CSVs and Database tables
raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

df_intents = pd.read_csv(
    os.path.join(raw_dir, "intents.csv"),
    parse_dates=["initiated_at"]
)

df_attempts_first = pd.read_csv(
    os.path.join(raw_dir, "attempts_first.csv"),
    parse_dates=["completed_at"],
    keep_default_na=False
)
df_attempts_first["error_code"] = df_attempts_first["error_code"].replace("", np.nan)
df_attempts_first["latency_ms"] = pd.to_numeric(df_attempts_first["latency_ms"], errors="coerce")
df_attempts_first["completed_at"] = pd.to_datetime(df_attempts_first["completed_at"], errors="coerce")

df_truth_first = pd.read_csv(
    os.path.join(raw_dir, "attempt_truth_first.csv"),
    keep_default_na=False
)
df_truth_first["original_error_code"] = df_truth_first["original_error_code"].replace("", np.nan)
df_truth_first["is_debited"] = df_truth_first["is_debited"].astype(bool)
df_truth_first["pending_converted"] = df_truth_first["pending_converted"].astype(bool)

df_fail_truth = pd.read_csv(
    os.path.join(raw_dir, "failure_truth.csv"),
    usecols=["intent_id", "incident_id"],
    keep_default_na=False
)
df_fail_truth["incident_id"] = df_fail_truth["incident_id"].replace("", np.nan)

# Database tables
load_dotenv()
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "paymentiq")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")
engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

dim_banks = pd.read_sql("SELECT bank_id, size_tier FROM dim_banks", engine)
customer_truth = pd.read_sql("SELECT customer_id, true_segment FROM truth.customer_truth", engine)

bank_tier_map = dict(zip(dim_banks["bank_id"], dim_banks["size_tier"]))
cust_seg_map = dict(zip(customer_truth["customer_id"], customer_truth["true_segment"]))

df_intents["size_tier"] = df_intents["bank_id"].map(bank_tier_map)
df_intents["true_segment"] = df_intents["customer_id"].map(cust_seg_map)

# Merge everything on intent_id into one table "first"
first = df_intents.merge(df_attempts_first, on="intent_id")
first = first.merge(df_truth_first, on="intent_id")
first = first.merge(df_fail_truth, on="intent_id")
first = first.sort_values("intent_id").reset_index(drop=True)

assert len(first) == 280000, f"Expected 280000 rows in first, got {len(first)}"
assert first["intent_id"].notna().all(), "Missing intent_id after merge"
assert first["customer_id"].notna().all(), "Missing customer_id after merge"
assert first["size_tier"].notna().all(), "Missing size_tier after merge"
assert first["true_segment"].notna().all(), "Missing true_segment after merge"

# c. FIRST ATTEMPTS
first["attempt_number"] = 1
first["was_debited"] = first["is_debited"].copy()
first["is_duplicate_debit"] = False

# d. CHAIN STATE
# chain_debited per intent = True if first.is_debited, or if first.status == "PENDING" and first.original_status == "SUCCESS"
chain_debited_arr = np.zeros(280001, dtype=bool)
init_chain_debited = (first["is_debited"].values) | (
    (first["status"].values == "PENDING") & (first["original_status"].values == "SUCCESS")
)
chain_debited_arr[first["intent_id"].values] = init_chain_debited

active_mask = first["status"].isin(["FAILED", "PENDING"]).values
cur = first[active_mask].copy()

# e. RETRY ROUNDS
all_retries = []

fail_code_keys = list(RETRY_FAIL_CODES.keys())
fail_code_weights = np.array(list(RETRY_FAIL_CODES.values()), dtype=float)
fail_code_p = fail_code_weights / fail_code_weights.sum()

outage_bank_id = [b[0] for b in BANKS if b[1] == OUTAGE_BANK][0]
deploy_psp_id = [p[0] for p in PSPS if p[1] == BAD_DEPLOY_PSP][0]
d_dep_start = date.fromisoformat(BAD_DEPLOY_START)
d_dep_end = date.fromisoformat(BAD_DEPLOY_END)
cutoff_time = pd.Timestamp("2026-09-30 23:59:59")

for r in range(1, RETRY_MAX + 1):
    n_cur = len(cur)
    if n_cur == 0:
        break

    # Exact random draws in exact specified order
    u_retry = rng.random(n_cur)
    u_gap_kind = rng.random(n_cur)
    z_gap = rng.standard_normal(n_cur)
    u_long = rng.random(n_cur)
    u_succ = rng.random(n_cur)
    u_same = rng.random(n_cur)
    fb_code = rng.choice(fail_code_keys, size=n_cur, p=fail_code_p)
    z_lat = rng.standard_normal(n_cur)
    u_pend = rng.random(n_cur)
    u_deb = rng.random(n_cur)

    # group
    cur_status = cur["status"].values
    cur_error = cur["error_code"].values
    group = np.where(
        cur_status == "PENDING",
        "pending",
        pd.Series(cur_error).map(RETRY_GROUP_OF).values
    )

    # retry_p
    base_retry_p = np.array([RETRY_PARAMS[g][0] for g in group])
    seg_retry_mult = cur["true_segment"].map(RETRY_SEGMENT_RETRY_MULT).values
    decay = RETRY_ROUND_DECAY ** (r - 1)
    retry_p = np.minimum(base_retry_p * seg_retry_mult * decay, RETRY_P_CAP)
    is_retried = u_retry < retry_p

    # gap seconds
    gap_long = (LONG_GAP_MIN_MIN + u_long * (LONG_GAP_MAX_MIN - LONG_GAP_MIN_MIN)) * 60.0
    gap_fast = np.clip(GAP_MEDIAN_S * np.exp(GAP_SIGMA * z_gap), GAP_MIN_S, GAP_MAX_FAST_S)
    gap_s = np.where(u_gap_kind < LONG_GAP_P, gap_long, gap_fast)
    gap_s = np.round(gap_s).astype(np.int64)

    # base time
    cur_completed = pd.to_datetime(cur["completed_at"])
    cur_initiated = pd.to_datetime(cur["initiated_at"])
    base_time = cur_completed.fillna(cur_initiated + pd.to_timedelta(PENDING_BASE_GAP_S, unit="s"))
    retry_init = base_time + pd.to_timedelta(gap_s, unit="s")

    # Drop (no retry) any row whose retry initiated_at is after cutoff
    retry_mask = is_retried & (retry_init <= cutoff_time)

    if not retry_mask.any():
        break

    ret = cur[retry_mask].copy()

    # Sliced random draws & computed variables for retrying rows
    u_succ_ret = u_succ[retry_mask]
    u_same_ret = u_same[retry_mask]
    fb_code_ret = fb_code[retry_mask]
    z_lat_ret = z_lat[retry_mask]
    u_pend_ret = u_pend[retry_mask]
    u_deb_ret = u_deb[retry_mask]
    group_ret = group[retry_mask]
    retry_init_ret = retry_init[retry_mask]

    # success_p
    base_succ_p = np.array([RETRY_PARAMS[g][1] for g in group_ret])
    seg_succ_mult = ret["true_segment"].map(RETRY_SEGMENT_SUCCESS_MULT).values
    success_p = base_succ_p * seg_succ_mult

    # Outage check
    is_outage_bank = (ret["bank_id"].values == outage_bank_id)
    in_outage_win = np.zeros(len(ret), dtype=bool)
    retry_init_series = pd.Series(retry_init_ret.values)
    for w_start, w_end in OUTAGE_WINDOWS:
        ts_start = pd.Timestamp(w_start)
        ts_end = pd.Timestamp(w_end)
        in_outage_win |= (retry_init_series >= ts_start) & (retry_init_series <= ts_end)
    is_outage_retry = is_outage_bank & in_outage_win

    success_p = np.where(is_outage_retry, success_p * OUTAGE_RETRY_SUCCESS_MULT, success_p)
    success_p = np.minimum(success_p, 0.98)

    succ_mask = u_succ_ret < success_p

    # Latency components
    net_mult = ret["network_type"].map(NET_LAT_MULT).values
    size_mult = ret["size_tier"].map(SIZE_LAT_MULT).values
    succ_lat = SUCCESS_LATENCY[0] * net_mult * size_mult * np.exp(SUCCESS_LATENCY[1] * z_lat_ret)

    # Failed retry error code
    cur_status_ret = ret["status"].values
    prev_error = np.where(
        cur_status_ret == "PENDING",
        ret["original_error_code"].values,
        ret["error_code"].values
    )
    has_prev_code = pd.Series(prev_error).notna().values & (prev_error != "")

    fail_code = np.where(
        is_outage_retry,
        np.where(u_same_ret < 0.9, "BNK_01", "BNK_04"),
        np.where(
            (u_same_ret < RETRY_SAME_CODE_P) & has_prev_code,
            prev_error,
            fb_code_ret
        )
    )

    # Failed retry latency
    lat_med = np.array([LATENCY_CODE[c][0] for c in fail_code])
    lat_sig = np.array([LATENCY_CODE[c][1] for c in fail_code])
    lat_use_mult = np.array([LATENCY_CODE[c][2] for c in fail_code])
    fail_mult = np.where(lat_use_mult, net_mult * size_mult, 1.0)
    fail_lat = lat_med * fail_mult * np.exp(lat_sig * z_lat_ret)

    retry_status = np.where(succ_mask, "SUCCESS", "FAILED")
    retry_error = np.where(succ_mask, np.nan, fail_code)
    retry_lat = np.where(succ_mask, succ_lat, fail_lat)

    retry_lat = np.clip(retry_lat, LATENCY_MIN, LATENCY_MAX)
    retry_lat_ms = np.round(retry_lat).astype(np.int64)
    retry_completed_at = retry_init_series + pd.to_timedelta(retry_lat_ms, unit="ms")

    # was_debited
    is_timeout = np.isin(retry_error, TIMEOUT_CODES)
    retry_was_debited = (~succ_mask) & is_timeout & (u_deb_ret < DEBITED_P)

    # PENDING for retries
    is_pending_code = np.isin(retry_error, PENDING_CODES)
    pend_from_failed = (~succ_mask) & is_pending_code & (u_pend_ret < PENDING_FROM_FAILED_P)
    pend_from_succ = succ_mask & (u_pend_ret < PENDING_FROM_SUCCESS_P)
    become_pending = pend_from_failed | pend_from_succ

    retry_orig_status = retry_status.copy()
    retry_orig_error = retry_error.copy()

    retry_status = np.where(become_pending, "PENDING", retry_status)
    retry_error = np.where(become_pending, np.nan, retry_error)
    retry_lat_ms_nullable = pd.Series(retry_lat_ms, dtype="Int64").where(~become_pending, pd.NA)
    retry_completed_at = retry_completed_at.where(~become_pending, pd.NaT)
    retry_was_debited = np.where(become_pending, False, retry_was_debited)

    # is_duplicate_debit & update chain_debited
    intent_ids_ret = ret["intent_id"].values
    prior_chain_debited = chain_debited_arr[intent_ids_ret]
    is_dup_debit = (retry_status == "SUCCESS") & prior_chain_debited

    new_chain_debit = retry_was_debited | ((retry_status == "PENDING") & (retry_orig_status == "SUCCESS"))
    chain_debited_arr[intent_ids_ret] |= new_chain_debit

    # incident_id
    retry_dates = retry_init_series.dt.date
    is_dep_psp = (ret["psp_id"].values == deploy_psp_id)
    is_dep_date = (retry_dates >= d_dep_start) & (retry_dates <= d_dep_end)
    is_deploy_retry = is_dep_psp & is_dep_date.values

    retry_incident_id = np.full(len(ret), np.nan, dtype=object)
    retry_incident_id[is_outage_retry] = "P1_OUTAGE"
    retry_incident_id[is_deploy_retry] = "P7_DEPLOY"

    ret["attempt_number"] = r + 1
    ret["initiated_at"] = retry_init_series.values
    ret["completed_at"] = retry_completed_at.values
    ret["status"] = retry_status
    ret["error_code"] = retry_error
    ret["latency_ms"] = retry_lat_ms_nullable.values
    ret["was_debited"] = retry_was_debited
    ret["original_status"] = retry_orig_status
    ret["original_error_code"] = retry_orig_error
    ret["incident_id"] = retry_incident_id
    ret["is_duplicate_debit"] = is_dup_debit

    all_retries.append(ret)

    # Next round's cur: failed retries only
    cur = ret[ret["status"] == "FAILED"].copy()

# f. FINALISE
attempts = pd.concat([first] + all_retries, ignore_index=True)
attempts = attempts.sort_values(by=["initiated_at", "intent_id", "attempt_number"]).reset_index(drop=True)
attempts["transaction_id"] = np.arange(1, len(attempts) + 1, dtype=np.int64)

# g. ASSERTS
# 1. transaction_id unique
assert attempts["transaction_id"].is_unique, "transaction_id not unique"

# 2. attempt_number between 1 and RETRY_MAX + 1
assert attempts["attempt_number"].between(1, RETRY_MAX + 1).all(), "attempt_number out of range"

# 3. within each intent: 1..k with no gaps, strictly increasing initiated_at, no attempt follows SUCCESS/PENDING retry or first SUCCESS
by_intent = attempts.sort_values(["intent_id", "attempt_number"]).reset_index(drop=True)
grp_cnt = by_intent.groupby("intent_id")["attempt_number"].count()
grp_max = by_intent.groupby("intent_id")["attempt_number"].max()
grp_min = by_intent.groupby("intent_id")["attempt_number"].min()
assert (grp_min == 1).all(), "Some intent does not start at attempt_number 1"
assert (grp_max == grp_cnt).all(), "Some intent has gaps in attempt_number"

is_retry = (by_intent["attempt_number"] > 1).values
prev_init = by_intent["initiated_at"].shift(1).values
curr_init = by_intent["initiated_at"].values
assert (curr_init[is_retry] > prev_init[is_retry]).all(), "initiated_at not strictly increasing"

is_att2 = (by_intent["attempt_number"] == 2).values
is_att_gt2 = (by_intent["attempt_number"] > 2).values
prev_status = by_intent["status"].shift(1).values
assert (prev_status[is_att2] != "SUCCESS").all(), "Attempt 2 followed attempt 1 with status SUCCESS"
assert (prev_status[is_att_gt2] == "FAILED").all(), "Retry attempt followed a non-FAILED retry"

# 4. no initiated_at after 2026-09-30 23:59:59
assert (attempts["initiated_at"] <= pd.Timestamp("2026-09-30 23:59:59")).all(), "initiated_at after cutoff"

# 5. every FAILED row has an error_code in FAILURE_CODES
valid_codes = set([c[0] for c in FAILURE_CODES])
failed_rows = attempts[attempts["status"] == "FAILED"]
assert failed_rows["error_code"].isin(valid_codes).all(), "Invalid error_code in FAILED attempts"

# 6. SUCCESS rows have no error_code
success_rows = attempts[attempts["status"] == "SUCCESS"]
assert success_rows["error_code"].isna().all(), "SUCCESS attempts have error_code"

# 7. PENDING rows have no error_code, latency_ms or completed_at
pending_rows = attempts[attempts["status"] == "PENDING"]
assert pending_rows["error_code"].isna().all(), "PENDING attempts have error_code"
assert pending_rows["latency_ms"].isna().all(), "PENDING attempts have latency_ms"
assert pending_rows["completed_at"].isna().all(), "PENDING attempts have completed_at"

# 8. every non-PENDING row has completed_at >= initiated_at and latency_ms within LATENCY_MIN..LATENCY_MAX
non_pending = attempts[attempts["status"] != "PENDING"]
assert (non_pending["completed_at"] >= non_pending["initiated_at"]).all(), "completed_at < initiated_at"
assert non_pending["latency_ms"].astype(float).between(LATENCY_MIN, LATENCY_MAX).all(), "latency_ms out of range"

# 9. amount between 1 and 100000
assert attempts["amount"].between(1, 100000).all(), "amount out of range"

# 10. attempt_number 1 rows match attempts_first.csv exactly on status and error_code
att1 = attempts[attempts["attempt_number"] == 1].sort_values("intent_id")
df_first_csv = pd.read_csv(os.path.join(raw_dir, "attempts_first.csv")).sort_values("intent_id")
assert (att1["status"].values == df_first_csv["status"].values).all(), "att1 status mismatch with attempts_first.csv"
assert (att1["error_code"].fillna("").values == df_first_csv["error_code"].fillna("").values).all(), "att1 error_code mismatch with attempts_first.csv"

# 11. total rows = 280000 + number of retry attempts
n_retries = (attempts["attempt_number"] > 1).sum()
assert len(attempts) == 280000 + n_retries, f"Expected {280000 + n_retries} rows, got {len(attempts)}"

# h. SAVE to data/raw/
# 1. attempts_all.csv
attempts_cols = [
    "transaction_id", "customer_id", "payee_id", "payee_category", "bank_id",
    "psp_id", "amount", "status", "error_code", "initiated_at", "completed_at",
    "latency_ms", "device_type", "network_type", "channel"
]
df_attempts_all = attempts[attempts_cols].copy()
df_attempts_all["initiated_at"] = pd.to_datetime(df_attempts_all["initiated_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
df_attempts_all["completed_at"] = pd.to_datetime(df_attempts_all["completed_at"]).dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
df_attempts_all["latency_ms"] = df_attempts_all["latency_ms"].astype("Int64")
df_attempts_all["error_code"] = df_attempts_all["error_code"].fillna("")
df_attempts_all.to_csv(os.path.join(raw_dir, "attempts_all.csv"), index=False)

# 2. transaction_truth.csv
df_txn_truth = attempts[["transaction_id", "intent_id", "is_duplicate_debit", "incident_id"]].copy()
df_txn_truth["incident_id"] = df_txn_truth["incident_id"].fillna("")
df_txn_truth.to_csv(os.path.join(raw_dir, "transaction_truth.csv"), index=False)

# 3. attempt_truth_all.csv
df_att_truth = attempts[["transaction_id", "intent_id", "attempt_number", "was_debited", "original_status"]].copy()
df_att_truth.to_csv(os.path.join(raw_dir, "attempt_truth_all.csv"), index=False)

# 4. intent_truth.csv
intent_n_att = attempts.groupby("intent_id")["attempt_number"].count()
succ_intents = set(attempts.loc[attempts["status"] == "SUCCESS", "intent_id"])

first_sorted = first.sort_values("intent_id").reset_index(drop=True)
df_intent_truth = pd.DataFrame({
    "intent_id": first_sorted["intent_id"],
    "customer_id": first_sorted["customer_id"],
    "repeat_of_intent_id": first_sorted["repeat_of_intent_id"].astype("Int64"),
    "first_status": first_sorted["status"],
    "n_attempts": first_sorted["intent_id"].map(intent_n_att),
    "final_outcome": np.where(first_sorted["intent_id"].isin(succ_intents), "SUCCESS", "NOT_SUCCESS")
})
df_intent_truth.to_csv(os.path.join(raw_dir, "intent_truth.csv"), index=False)

# i. PRINT checks
print("=== 1. Attempt & Retry Counts ===")
att_counts = attempts["attempt_number"].value_counts().sort_index()
print(f"Total attempts:                   {len(attempts):,}")
print(f"Retry attempts:                   {n_retries:,}")
for att_num in [2, 3, 4]:
    print(f"  Attempt {att_num}:                      {att_counts.get(att_num, 0):,}")
n_intents_retried = (attempts.groupby("intent_id")["attempt_number"].max() > 1).sum()
print(f"Intents with >= 1 retry:          {n_intents_retried:,}")

print("\n=== 2. Round-1 Retry Behaviour by Group ===")
first_elig = first[first["status"].isin(["FAILED", "PENDING"])].copy()
first_elig["group"] = np.where(
    first_elig["status"] == "PENDING",
    "pending",
    first_elig["error_code"].map(RETRY_GROUP_OF)
)

att2_rows = attempts[attempts["attempt_number"] == 2]
att2_by_intent = dict(zip(att2_rows["intent_id"], att2_rows["status"]))

first_elig["att2_status"] = first_elig["intent_id"].map(att2_by_intent)
first_elig["did_retry"] = first_elig["att2_status"].notna()
first_elig["retry_succ"] = first_elig["att2_status"] == "SUCCESS"

groups_order = ["wrong_pin", "funds", "limit", "safe", "verify", "donot", "escalate", "customer_other", "pending"]
print(f"{'Group':<16} {'Eligible':<10} {'Retries':<10} {'Retry Rate':<12} {'Success Rate':<12}")
for g in groups_order:
    sub = first_elig[first_elig["group"] == g]
    n_el = len(sub)
    n_ret = sub["did_retry"].sum()
    r_rate = (n_ret / n_el * 100) if n_el > 0 else 0.0
    s_rate = (sub["retry_succ"].sum() / n_ret * 100) if n_ret > 0 else 0.0
    print(f"{g:<16} {n_el:<10} {n_ret:<10} {r_rate:>8.2f}%   {s_rate:>8.2f}%")

tot_el = len(first_elig)
tot_ret = first_elig["did_retry"].sum()
ov_r_rate = tot_ret / tot_el * 100
ov_s_rate = first_elig["retry_succ"].sum() / tot_ret * 100
print(f"{'OVERALL':<16} {tot_el:<10} {tot_ret:<10} {ov_r_rate:>8.2f}%   {ov_s_rate:>8.2f}%")

print("\n=== 3. Round-1 Retry Rate & Success Rate by True Segment ===")
print(f"{'True Segment':<18} {'Eligible':<10} {'Retries':<10} {'Retry Rate':<12} {'Success Rate':<12}")
for seg in ["Reliable", "Retry-dependent", "Failure-prone", "Abandoning", "High-value"]:
    sub = first_elig[first_elig["true_segment"] == seg]
    n_el = len(sub)
    n_ret = sub["did_retry"].sum()
    r_rate = (n_ret / n_el * 100) if n_el > 0 else 0.0
    s_rate = (sub["retry_succ"].sum() / n_ret * 100) if n_ret > 0 else 0.0
    print(f"{seg:<18} {n_el:<10} {n_ret:<10} {r_rate:>8.2f}%   {s_rate:>8.2f}%")

print("\n=== 4. Retry Gap (Attempt 2) ===")
# Base time of previous attempt (completed_at if not missing, else initiated_at)
first_comp_map = dict(zip(first["intent_id"], first["completed_at"]))
first_init_map = dict(zip(first["intent_id"], first["initiated_at"]))

att2_prev_comp = pd.Series(att2_rows["intent_id"].map(first_comp_map))
att2_prev_init = pd.Series(att2_rows["intent_id"].map(first_init_map))
att2_base_time = att2_prev_comp.fillna(att2_prev_init)
retry_gaps_s = (pd.to_datetime(att2_rows["initiated_at"].values) - pd.to_datetime(att2_base_time.values)).total_seconds()

med_gap = np.median(retry_gaps_s)
share_gt_1800 = (retry_gaps_s > 1800).mean() * 100
print(f"Median gap:                       {med_gap:.1f} seconds")
print(f"Share above 1,800s (30m):         {share_gt_1800:.2f}%")

print("\n=== 5. Kestrel Commercial Retries (Attempt 2) ===")
kestrel_att2 = att2_rows[att2_rows["bank_id"] == outage_bank_id].copy()
kestrel_init = pd.to_datetime(kestrel_att2["initiated_at"])
in_kest_outage = np.zeros(len(kestrel_att2), dtype=bool)
for w_start, w_end in OUTAGE_WINDOWS:
    ts_start = pd.Timestamp(w_start)
    ts_end = pd.Timestamp(w_end)
    in_kest_outage |= (kestrel_init >= ts_start) & (kestrel_init <= ts_end)

k_in_cnt = in_kest_outage.sum()
k_in_succ = (kestrel_att2.loc[in_kest_outage, "status"] == "SUCCESS").sum()
k_in_rate = (k_in_succ / k_in_cnt * 100) if k_in_cnt > 0 else 0.0

k_out_cnt = (~in_kest_outage).sum()
k_out_succ = (kestrel_att2.loc[~in_kest_outage, "status"] == "SUCCESS").sum()
k_out_rate = (k_out_succ / k_out_cnt * 100) if k_out_cnt > 0 else 0.0

print(f"Inside Outage Windows:  Count = {k_in_cnt:>5}, Success Rate = {k_in_rate:.2f}%")
print(f"Outside Outage Windows: Count = {k_out_cnt:>5}, Success Rate = {k_out_rate:.2f}%")

print("\n=== 6. Status Shares & Failure Rates ===")
stat_counts = attempts["status"].value_counts()
n_tot = len(attempts)
print(f"Overall SUCCESS share:            {stat_counts.get('SUCCESS', 0) / n_tot * 100:.2f}% ({stat_counts.get('SUCCESS', 0):,})")
print(f"Overall FAILED share:             {stat_counts.get('FAILED', 0) / n_tot * 100:.2f}% ({stat_counts.get('FAILED', 0):,})")
print(f"Overall PENDING share:            {stat_counts.get('PENDING', 0) / n_tot * 100:.2f}% ({stat_counts.get('PENDING', 0):,})")

overall_elig = attempts[attempts["status"].isin(["SUCCESS", "FAILED"])]
fail_rate_overall = (overall_elig["status"] == "FAILED").mean() * 100
print(f"Failure rate (eligible, overall): {fail_rate_overall:.2f}%")

att1_elig = attempts[(attempts["attempt_number"] == 1) & attempts["status"].isin(["SUCCESS", "FAILED"])]
fail_rate_att1 = (att1_elig["status"] == "FAILED").mean() * 100
print(f"Failure rate (eligible, Att 1):   {fail_rate_att1:.2f}%")

ret_elig = attempts[(attempts["attempt_number"] > 1) & attempts["status"].isin(["SUCCESS", "FAILED"])]
fail_rate_ret = (ret_elig["status"] == "FAILED").mean() * 100
print(f"Failure rate (eligible, Retries): {fail_rate_ret:.2f}%")

print("\n=== 7. Failed-First Recovery Rates ===")
failed_first = first[first["status"] == "FAILED"]
rec_elig_intents = failed_first[~failed_first["error_code"].isin(["CUS_03", "TEC_01", "RSK_01"])]

final_outcome_map = dict(zip(df_intent_truth["intent_id"], df_intent_truth["final_outcome"]))
n_attempts_map = dict(zip(df_intent_truth["intent_id"], df_intent_truth["n_attempts"]))

rec_elig_outcomes = pd.Series(rec_elig_intents["intent_id"].map(final_outcome_map))
rec_elig_n_att = pd.Series(rec_elig_intents["intent_id"].map(n_attempts_map))

rec_rate_elig = (rec_elig_outcomes == "SUCCESS").mean() * 100
rec_rate_all_failed = (pd.Series(failed_first["intent_id"].map(final_outcome_map)) == "SUCCESS").mean() * 100
never_retried_share = (rec_elig_n_att == 1).mean() * 100

print(f"Recovery rate (Eligible Failed-First): {rec_rate_elig:.2f}%")
print(f"Recovery rate (All Failed-First):      {rec_rate_all_failed:.2f}%")
print(f"Never Retried Share (Eligible):        {never_retried_share:.2f}%")

print("\n=== 8. Double Charges (is_duplicate_debit) ===")
dup_rows = attempts[attempts["is_duplicate_debit"] == True]
print(f"Total is_duplicate_debit rows:         {len(dup_rows):,}")

dup_intents = set(dup_rows["intent_id"])
dup_first = first[first["intent_id"].isin(dup_intents)]

from_timeout = (dup_first["is_debited"] == True).sum()
from_pending_succ = ((dup_first["status"] == "PENDING") & (dup_first["original_status"] == "SUCCESS")).sum()
print(f"  Source = debited timeout:            {from_timeout}")
print(f"  Source = PENDING originally SUCCESS: {from_pending_succ}")

debited_timeouts = first[first["is_debited"] == True]
deb_timeout_retried = debited_timeouts[debited_timeouts["intent_id"].map(n_attempts_map) > 1]
n_deb_retried = len(deb_timeout_retried)
deb_retries = attempts[(attempts["attempt_number"] > 1) & attempts["intent_id"].isin(deb_timeout_retried["intent_id"])]
deb_retries_succ_share = (deb_retries["status"] == "SUCCESS").mean() * 100
print(f"Debited-timeout first attempts retried: {n_deb_retried} / {len(debited_timeouts)}")
print(f"Share of those retries that succeeded:  {deb_retries_succ_share:.2f}%")

print("\n=== 9. n_attempts Distribution Over Intents ===")
n_att_dist = df_intent_truth["n_attempts"].value_counts().sort_index()
for k, cnt in n_att_dist.items():
    pct = cnt / len(df_intent_truth) * 100
    print(f"  {k} attempt(s): {cnt:>6} ({pct:>5.2f}%)")

print("\nRetries generated OK")
