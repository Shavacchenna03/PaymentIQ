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

rng = np.random.default_rng(SEED + 3)

# b. Load intents.csv, first_attempts.csv, dim_banks
raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
df_intents = pd.read_csv(
    os.path.join(raw_dir, "intents.csv"),
    usecols=["intent_id", "initiated_at", "bank_id", "psp_id", "network_type"],
    parse_dates=["initiated_at"]
)
df_first = pd.read_csv(
    os.path.join(raw_dir, "first_attempts.csv"),
    usecols=["intent_id", "status", "error_code"],
    keep_default_na=False
)
df_first["error_code"] = df_first["error_code"].replace("", np.nan)

load_dotenv()
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "paymentiq")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")
engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

dim_banks = pd.read_sql("SELECT bank_id, size_tier FROM dim_banks", engine)

df = df_intents.merge(df_first, on="intent_id").merge(dim_banks, on="bank_id")
df = df.sort_values("intent_id").reset_index(drop=True)

assert len(df) == 280000, f"Expected 280000 rows, got {len(df)}"
assert df["intent_id"].notna().all(), "Missing intent_id after merge"

# c. Original status & error code
df["original_status"] = df["status"].copy()
df["original_error_code"] = df["error_code"].copy()

# d. Draws in exact order
n = len(df)
u1 = rng.random(n)
z = rng.standard_normal(n)
u2 = rng.random(n)

# e. PENDING conversion
is_failed_pending_candidate = (df["original_status"] == "FAILED") & (df["original_error_code"].isin(PENDING_CODES))
is_success_pending_candidate = (df["original_status"] == "SUCCESS")

is_pending = (
    (is_failed_pending_candidate & (u1 < PENDING_FROM_FAILED_P)) |
    (is_success_pending_candidate & (u1 < PENDING_FROM_SUCCESS_P))
)

df["pending_converted"] = is_pending
df.loc[is_pending, "status"] = "PENDING"
df.loc[is_pending, "error_code"] = np.nan

# f. LATENCY for non-PENDING rows
deploy_psp_id = [p[0] for p in PSPS if p[1] == BAD_DEPLOY_PSP][0]
d_dep_start = date.fromisoformat(BAD_DEPLOY_START)
d_dep_end = date.fromisoformat(BAD_DEPLOY_END)
dep_window_days = (d_dep_end - d_dep_start).days

intent_dates = df["initiated_at"].dt.date
days_into_deploy = (pd.to_datetime(intent_dates) - pd.to_datetime(d_dep_start)).dt.days.values.astype(float)
is_dep_psp = (df["psp_id"].values == deploy_psp_id)
is_in_dep_window = (intent_dates >= d_dep_start) & (intent_dates <= d_dep_end)
is_timeout_fail = (df["status"] == "FAILED") & (df["error_code"].isin(TIMEOUT_CODES))

is_deploy_affected = is_dep_psp & is_in_dep_window.values & (~is_timeout_fail)
deploy_mult = np.where(is_deploy_affected, 1.0 + (DEPLOY_LATENCY_PEAK_MULT - 1.0) * (days_into_deploy / dep_window_days), 1.0)

code_med_map = {c: LATENCY_CODE[c][0] for c in LATENCY_CODE}
code_sig_map = {c: LATENCY_CODE[c][1] for c in LATENCY_CODE}
code_mult_map = {c: LATENCY_CODE[c][2] for c in LATENCY_CODE}

eff_status = df["status"].values
eff_error = df["error_code"].fillna("BNK_01").values

median_arr = np.where(eff_status == "SUCCESS", SUCCESS_LATENCY[0], pd.Series(eff_error).map(code_med_map).values)
sigma_arr = np.where(eff_status == "SUCCESS", SUCCESS_LATENCY[1], pd.Series(eff_error).map(code_sig_map).values)
use_mult_arr = np.where(eff_status == "SUCCESS", True, pd.Series(eff_error).map(code_mult_map).values).astype(bool)

net_mult_val = df["network_type"].map(NET_LAT_MULT).values
size_mult_val = df["size_tier"].map(SIZE_LAT_MULT).values

net_mult = np.where(use_mult_arr, net_mult_val, 1.0)
size_mult = np.where(use_mult_arr, size_mult_val, 1.0)

lat = median_arr * net_mult * size_mult * deploy_mult * np.exp(sigma_arr * z)
lat = np.clip(lat, LATENCY_MIN, LATENCY_MAX)

df["latency_ms"] = pd.Series(np.nan, index=df.index, dtype="Int64")
non_pending_mask = ~is_pending
df.loc[non_pending_mask, "latency_ms"] = np.round(lat[non_pending_mask]).astype(int)

# g. completed_at
df["completed_at"] = df["initiated_at"] + pd.to_timedelta(df["latency_ms"].fillna(0), unit="ms")
df.loc[is_pending, "completed_at"] = pd.NaT

# h. DEBITED (P12)
is_debited = (df["status"] == "FAILED") & (df["error_code"].isin(TIMEOUT_CODES)) & (u2 < DEBITED_P)
df["is_debited"] = is_debited

# i. ASSERTS
assert len(df) == 280000, f"Expected 280000 rows, got {len(df)}"

pending_rows = df[df["status"] == "PENDING"]
assert pending_rows["error_code"].isna().all(), "PENDING rows must have missing error_code"
assert pending_rows["latency_ms"].isna().all(), "PENDING rows must have missing latency_ms"
assert pending_rows["completed_at"].isna().all(), "PENDING rows must have missing completed_at"

success_rows = df[df["status"] == "SUCCESS"]
assert success_rows["error_code"].isna().all(), "SUCCESS rows must have missing error_code"

failed_rows = df[df["status"] == "FAILED"]
valid_codes = set(fc[0] for fc in FAILURE_CODES)
assert failed_rows["error_code"].isin(valid_codes).all(), "Every FAILED row must have a valid error_code"

non_pending = df[df["status"] != "PENDING"]
assert ((non_pending["latency_ms"] >= LATENCY_MIN) & (non_pending["latency_ms"] <= LATENCY_MAX)).all(), "latency_ms out of bounds"
assert (non_pending["completed_at"] >= non_pending["initiated_at"]).all(), "completed_at must be >= initiated_at"

debited_rows = df[df["is_debited"]]
assert (debited_rows["status"] == "FAILED").all(), "is_debited rows must be FAILED"
assert (debited_rows["error_code"].isin(TIMEOUT_CODES)).all(), "is_debited rows must have TIMEOUT_CODES"

# j. Save CSVs
df_attempts_first = df[["intent_id", "status", "error_code", "latency_ms", "completed_at"]]
df_attempts_first.to_csv(os.path.join(raw_dir, "attempts_first.csv"), index=False)

df_truth_first = df[["intent_id", "original_status", "original_error_code", "pending_converted", "is_debited"]]
df_truth_first.to_csv(os.path.join(raw_dir, "attempt_truth_first.csv"), index=False)

# k. PRINT CHECKS
print("=== 1. Attempt Status & Pending Breakdown ===")
status_counts = df["status"].value_counts()
status_shares = df["status"].value_counts(normalize=True) * 100
for st in ["SUCCESS", "FAILED", "PENDING"]:
    cnt = status_counts.get(st, 0)
    sh = status_shares.get(st, 0.0)
    print(f"  {st:8s}: {cnt:6d} ({sh:.2f}%)")

pending_share = (df["status"] == "PENDING").mean() * 100
orig_failed_pending = ((df["status"] == "PENDING") & (df["original_status"] == "FAILED")).sum()
orig_success_pending = ((df["status"] == "PENDING") & (df["original_status"] == "SUCCESS")).sum()
n_succ = (df["status"] == "SUCCESS").sum()
n_fail = (df["status"] == "FAILED").sum()
fail_rate_eligible = n_fail / (n_succ + n_fail) * 100

print(f"Pending share of all attempts: {pending_share:.2f}%")
print(f"PENDING originally FAILED:     {orig_failed_pending}")
print(f"PENDING originally SUCCESS:    {orig_success_pending}")
print(f"Failure rate on eligible attempts: {fail_rate_eligible:.2f}%")

print("\n=== 2. Latency Percentiles ===")
succ_lat = df.loc[df["status"] == "SUCCESS", "latency_ms"].dropna().values.astype(float)
elig_lat = df.loc[df["status"].isin(["SUCCESS", "FAILED"]), "latency_ms"].dropna().values.astype(float)

print(f"SUCCESS Latency:        Median = {np.median(succ_lat):.0f} ms, P95 = {np.percentile(succ_lat, 95):.0f} ms")
print(f"SUCCESS+FAILED Latency: P50 = {np.percentile(elig_lat, 50):.0f} ms, P95 = {np.percentile(elig_lat, 95):.0f} ms, P99 = {np.percentile(elig_lat, 99):.0f} ms")
pct_10s = (elig_lat >= 10000).mean() * 100
print(f"Share of eligible attempts >= 10,000 ms: {pct_10s:.2f}%")

print("\n=== 3. Median Latency by Error Code (ms) ===")
check_codes = ["NET_01", "NET_02", "NET_03", "BNK_04", "BNK_01", "PSP_01", "CUS_01", "CUS_05"]
for cd in check_codes:
    med = df.loc[df["error_code"] == cd, "latency_ms"].median()
    print(f"  {cd}: {med:.0f} ms")

print("\n=== 4. SUCCESS Median Latency by Network & Size Tier ===")
net_order = ["WiFi", "5G", "4G", "3G", "2G"]
net_succ_med = df[df["status"] == "SUCCESS"].groupby("network_type")["latency_ms"].median().reindex(net_order)
for net, med in net_succ_med.items():
    print(f"  {net:5s}: {med:.0f} ms")
ratio_2g_wifi = net_succ_med["2G"] / net_succ_med["WiFi"]
print(f"Ratio 2G / WiFi: {ratio_2g_wifi:.2f}x")

tier_order = ["Large", "Medium", "Small"]
tier_succ_med = df[df["status"] == "SUCCESS"].groupby("size_tier")["latency_ms"].median().reindex(tier_order)
for t, med in tier_succ_med.items():
    print(f"  {t:7s}: {med:.0f} ms")
print(f"Ratio Medium / Large: {tier_succ_med['Medium'] / tier_succ_med['Large']:.2f}x")
print(f"Ratio Small / Large:  {tier_succ_med['Small'] / tier_succ_med['Large']:.2f}x")

print("\n=== 5. Clearwave SUCCESS Median Latency Across Deploy Periods ===")
cw_succ = df[(df["psp_id"] == deploy_psp_id) & (df["status"] == "SUCCESS")].copy()
cw_succ["date"] = cw_succ["initiated_at"].dt.date

p1_mask = (cw_succ["date"] >= date.fromisoformat("2026-07-24")) & (cw_succ["date"] <= date.fromisoformat("2026-08-02"))
p2_mask = (cw_succ["date"] >= date.fromisoformat("2026-08-03")) & (cw_succ["date"] <= date.fromisoformat("2026-08-05"))
p3_mask = (cw_succ["date"] >= date.fromisoformat("2026-08-14")) & (cw_succ["date"] <= date.fromisoformat("2026-08-16"))
p4_mask = (cw_succ["date"] >= date.fromisoformat("2026-08-17")) & (cw_succ["date"] <= date.fromisoformat("2026-08-26"))

m_p1 = cw_succ.loc[p1_mask, "latency_ms"].median()
m_p2 = cw_succ.loc[p2_mask, "latency_ms"].median()
m_p3 = cw_succ.loc[p3_mask, "latency_ms"].median()
m_p4 = cw_succ.loc[p4_mask, "latency_ms"].median()

print(f"  Period 1 (24 Jul - 02 Aug, Pre-deploy):  {m_p1:.0f} ms (ratio: 1.00x)")
print(f"  Period 2 (03 Aug - 05 Aug, Deploy start): {m_p2:.0f} ms (ratio: {m_p2 / m_p1:.2f}x)")
print(f"  Period 3 (14 Aug - 16 Aug, Deploy peak):  {m_p3:.0f} ms (ratio: {m_p3 / m_p1:.2f}x)")
print(f"  Period 4 (17 Aug - 26 Aug, Post-fix):     {m_p4:.0f} ms (ratio: {m_p4 / m_p1:.2f}x)")

print("\n=== 6. Failure Rate by Latency Band ===")
elig_df = df[df["status"].isin(["SUCCESS", "FAILED"])].copy()
b1 = elig_df["latency_ms"] < 2000
b2 = (elig_df["latency_ms"] >= 2000) & (elig_df["latency_ms"] < 5000)
b3 = (elig_df["latency_ms"] >= 5000) & (elig_df["latency_ms"] < 10000)
b4 = elig_df["latency_ms"] >= 10000

bands = [
    ("Under 2000 ms", b1),
    ("2000 to 4999 ms", b2),
    ("5000 to 9999 ms", b3),
    ("10000 ms and above", b4)
]

for b_name, b_mask in bands:
    cnt = b_mask.sum()
    fr = (elig_df.loc[b_mask, "status"] == "FAILED").mean() * 100 if cnt > 0 else 0
    print(f"  {b_name:20s}: Count = {cnt:6d}, Failure Rate = {fr:.2f}%")

print("\n=== 7. Debited (P12) Flag Counts ===")
print(f"Total is_debited count: {df['is_debited'].sum()}")
deb_by_code = df[df["is_debited"]]["error_code"].value_counts()
for cd, cnt in deb_by_code.items():
    print(f"  {cd}: {cnt}")

print("\nLatency and pending generated OK")
