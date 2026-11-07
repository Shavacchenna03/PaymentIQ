import os
import sys
from datetime import date, datetime
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# a. Imports & RNG
sys.path.insert(0, os.path.dirname(__file__))
from config import *

rng = np.random.default_rng(SEED + 2)

# Helper functions
def logit(p):
    return np.log(p / (1.0 - p))

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))

def calibrate(offset, target, n_iter=60, low=-15.0, high=5.0):
    c_low, c_high = low, high
    for _ in range(n_iter):
        c_mid = (c_low + c_high) / 2.0
        val = np.mean(sigmoid(offset + c_mid))
        if val < target:
            c_low = c_mid
        else:
            c_high = c_mid
    c_final = (c_low + c_high) / 2.0
    achieved = np.mean(sigmoid(offset + c_final))
    return c_final, achieved

# b. Load intents.csv, dim_banks, truth.customer_truth
intents_path = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "intents.csv")
df = pd.read_csv(intents_path, parse_dates=["initiated_at"])

load_dotenv()
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "paymentiq")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")

engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

dim_banks = pd.read_sql("SELECT bank_id, bank_name, size_tier FROM dim_banks", engine)
customer_truth = pd.read_sql("SELECT customer_id, true_segment FROM truth.customer_truth", engine)

bank_name_map = dict(zip(dim_banks["bank_id"], dim_banks["bank_name"]))
bank_tier_map = dict(zip(dim_banks["bank_id"], dim_banks["size_tier"]))
cust_seg_map = dict(zip(customer_truth["customer_id"], customer_truth["true_segment"]))

df["bank_name"] = df["bank_id"].map(bank_name_map)
df["size_tier"] = df["bank_id"].map(bank_tier_map)
df["true_segment"] = df["customer_id"].map(cust_seg_map)

# c. Date features
d_start = date.fromisoformat(START_DATE)
d_end = date.fromisoformat(END_DATE)
n_days = (d_end - d_start).days + 1

intent_dates = df["initiated_at"].dt.date
day_index = (pd.to_datetime(intent_dates) - pd.to_datetime(d_start)).dt.days.values.astype(float)
trend = TREND_LOGODDS * day_index / (n_days - 1)
day_of_month = df["initiated_at"].dt.day.values
month_end = ((day_of_month >= 28) | (day_of_month <= 2)).astype(float)
hour = df["initiated_at"].dt.hour.values

# d. LOGIT OFFSETS per intent
bank_base_logit = np.array([logit(BANK_BASE_FAIL[t]) for t in df["size_tier"].values])
zenora_penalty = np.where(df["bank_name"].values == HIDDEN_BAD_BANK, HIDDEN_BAD_BANK_LOGODDS_PENALTY, 0.0)
is_peak = np.isin(hour, PEAK_HOURS)
peak_penalty = np.where(is_peak, np.array([PEAK_LOGODDS[t] for t in df["size_tier"].values]), 0.0)

bank_off = bank_base_logit + zenora_penalty + peak_penalty + trend + MONTH_END_LOGODDS * month_end

net_base = np.array([NET_LOGODDS[net] for net in df["network_type"].values])
net_off = net_base + trend

cust_off = np.array([SEGMENT_CUSTOMER_LOGODDS[s] for s in df["true_segment"].values])

psp_off = trend + MONTH_END_LOGODDS * month_end

# e. CALIBRATION
c_bank, ach_bank = calibrate(bank_off, FAMILY_TARGET["bank"])
c_net, ach_net = calibrate(net_off, FAMILY_TARGET["network"])
c_cust, ach_cust = calibrate(cust_off, FAMILY_TARGET["customer"])
c_psp, ach_psp = calibrate(psp_off, FAMILY_TARGET["psp"])

p_bank = sigmoid(bank_off + c_bank)
p_network = sigmoid(net_off + c_net)
p_customer = sigmoid(cust_off + c_cust)
p_psp = sigmoid(psp_off + c_psp)

print("=== Calibration Results ===")
print(f"Bank:     c = {c_bank:.4f}, target = {FAMILY_TARGET['bank']:.4f}, achieved = {ach_bank:.4f}")
print(f"Network:  c = {c_net:.4f}, target = {FAMILY_TARGET['network']:.4f}, achieved = {ach_net:.4f}")
print(f"Customer: c = {c_cust:.4f}, target = {FAMILY_TARGET['customer']:.4f}, achieved = {ach_cust:.4f}")
print(f"PSP:      c = {c_psp:.4f}, target = {FAMILY_TARGET['psp']:.4f}, achieved = {ach_psp:.4f}")

# f. OTHER FAMILY PROBABILITIES
p0_risk = FIXED_FAMILY_P["risk"]
odds0_risk = p0_risk / (1.0 - p0_risk)
odds_risk = np.where(df["amount"].values > RISK_AMOUNT_THRESHOLD, odds0_risk * RISK_AMOUNT_ODDS_MULT, odds0_risk)
p_risk = odds_risk / (1.0 + odds_risk)

p_technical = np.full(len(df), FIXED_FAMILY_P["technical"])
p_unknown = np.full(len(df), FIXED_FAMILY_P["unknown"])

txn_limits = np.array([PER_TXN_LIMIT[t] for t in df["size_tier"].values])
p_limit_02 = np.where(df["amount"].values > txn_limits, P_LIM02, 0.0)

# limit_01: sort by customer_id then initiated_at, compute daily_cum
df["txn_date"] = intent_dates
df["orig_idx"] = np.arange(len(df))
sorted_df = df.sort_values(["customer_id", "initiated_at"]).copy()
sorted_df["daily_cum"] = sorted_df.groupby(["customer_id", "txn_date"])["amount"].cumsum()
daily_cum = sorted_df.sort_values("orig_idx")["daily_cum"].values
p_limit_01 = np.where(daily_cum > DAILY_LIMIT, P_LIM01, 0.0)

is_lim03_cat = df["payee_category"].isin(LIM03_CATEGORIES).values
is_lim03_amt = (df["amount"].values > LIM03_AMOUNT)
p_limit_03 = np.where(is_lim03_cat & is_lim03_amt, P_LIM03, 0.0)

# outage
outage_mask = np.zeros(len(df), dtype=bool)
is_outage_bank = (df["bank_name"].values == OUTAGE_BANK)
for w_start, w_end in OUTAGE_WINDOWS:
    ts_start = pd.Timestamp(w_start)
    ts_end = pd.Timestamp(w_end)
    in_win = (df["initiated_at"] >= ts_start) & (df["initiated_at"] <= ts_end)
    outage_mask |= (is_outage_bank & in_win.values)
p_outage = np.where(outage_mask, OUTAGE_P, 0.0)

# deploy
deploy_psp_id = [p[0] for p in PSPS if p[1] == BAD_DEPLOY_PSP][0]
d_dep_start = date.fromisoformat(BAD_DEPLOY_START)
d_dep_end = date.fromisoformat(BAD_DEPLOY_END)
is_dep_psp = (df["psp_id"].values == deploy_psp_id)
is_dep_date = (intent_dates >= d_dep_start) & (intent_dates <= d_dep_end)
deploy_mask = is_dep_psp & is_dep_date.values
p_deploy = np.where(deploy_mask, DEPLOY_P, 0.0)

# g. incident_id
incident_id = np.full(len(df), "", dtype=object)
incident_id[outage_mask] = "P1_OUTAGE"
incident_id[deploy_mask] = "P7_DEPLOY"

# h. FAMILIES
family_names = [
    "bank", "network", "customer", "psp", "risk", "technical",
    "unknown", "limit_02", "limit_01", "limit_03", "outage", "deploy"
]
P = np.column_stack([
    p_bank, p_network, p_customer, p_psp, p_risk, p_technical,
    p_unknown, p_limit_02, p_limit_01, p_limit_03, p_outage, p_deploy
])

n, k = P.shape
fired = rng.random((n, k)) < P
has_failed = fired.any(axis=1)

weights = P * fired
row_sums = weights.sum(axis=1)
r = rng.random(n) * row_sums
cum_w = np.cumsum(weights, axis=1)

chosen_family_idx = np.sum(cum_w <= r[:, None], axis=1)
chosen_family_idx = np.clip(chosen_family_idx, 0, k - 1)

# i. CODE per family
status = np.where(has_failed, "FAILED", "SUCCESS")
error_code = np.full(n, "", dtype=object)
error_family = np.full(n, "", dtype=object)

for idx, fam in enumerate(family_names):
    fam_mask = has_failed & (chosen_family_idx == idx)
    n_fam = fam_mask.sum()
    if n_fam > 0:
        error_family[fam_mask] = fam
        codes = list(FAMILY_CODES[fam].keys())
        w_codes = list(FAMILY_CODES[fam].values())
        p_codes = np.array(w_codes, dtype=float) / sum(w_codes)
        error_code[fam_mask] = rng.choice(codes, size=n_fam, p=p_codes)

# j. Save data/raw/first_attempts.csv and data/raw/failure_truth.csv
raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

df_first = pd.DataFrame({
    "intent_id": df["intent_id"],
    "status": status,
    "error_code": error_code
})
df_first.to_csv(os.path.join(raw_dir, "first_attempts.csv"), index=False)

df_truth = pd.DataFrame({
    "intent_id": df["intent_id"],
    "error_family": error_family,
    "incident_id": incident_id,
    "p_bank": p_bank,
    "p_network": p_network,
    "p_customer": p_customer,
    "p_psp": p_psp
})
df_truth.to_csv(os.path.join(raw_dir, "failure_truth.csv"), index=False)

# k. ASSERTS
valid_codes = set(fc[0] for fc in FAILURE_CODES)
assert (df_first.loc[df_first["status"] == "FAILED", "error_code"].isin(valid_codes)).all(), "Invalid error code in FAILED rows"
assert (df_first.loc[df_first["status"] == "SUCCESS", "error_code"] == "").all(), "Non-empty error code in SUCCESS rows"
assert len(df_first) == len(df), "first_attempts row count mismatch"
assert len(df_truth) == len(df), "failure_truth row count mismatch"

# l. PRINT CHECKS
df["status"] = status
df["error_code"] = error_code
df["error_family"] = error_family

total_intents = len(df)
total_failed = (status == "FAILED").sum()
overall_fail_rate = total_failed / total_intents * 100

print("\n=== 1. Overall Failure Rate & Common Codes ===")
print(f"Overall failure rate: {overall_fail_rate:.2f}% ({total_failed} / {total_intents})")
print("\nFailure share by error family (% of all failures):")
fam_shares = df.loc[df["status"] == "FAILED", "error_family"].value_counts(normalize=True) * 100
for f_name, f_sh in fam_shares.items():
    print(f"  {f_name:12s}: {f_sh:.2f}%")

print("\nTop 10 most common error codes (% of all failures):")
top10_codes = df.loc[df["status"] == "FAILED", "error_code"].value_counts().head(10)
for c_name, c_cnt in top10_codes.items():
    c_sh = c_cnt / total_failed * 100
    print(f"  {c_name:8s}: {c_cnt:6d} ({c_sh:.2f}%)")

print("\n=== 2. Failure Rate by Month ===")
months = ["April", "May", "June", "July", "August", "September"]
df["month"] = df["initiated_at"].dt.month_name()
month_fail = df.groupby("month")["status"].apply(lambda s: (s == "FAILED").mean() * 100).reindex(months)
for m, r_val in month_fail.items():
    print(f"  {m:10s}: {r_val:.2f}%")
diff_pts = month_fail["September"] - month_fail["April"]
print(f"September minus April: {diff_pts:+.2f} percentage points")

print("\n=== 3. Failure Rate by Size Tier & Large Bank Breakdown ===")
tier_fail = df.groupby("size_tier")["status"].apply(lambda s: (s == "FAILED").mean() * 100).reindex(["Large", "Medium", "Small"])
for t, r_val in tier_fail.items():
    print(f"  {t:10s}: {r_val:.2f}%")

other_large_mask = (df["size_tier"] == "Large") & (~df["bank_name"].isin(["Tarang National", "Zenora", OUTAGE_BANK]))
tarang_mask = (df["bank_name"] == "Tarang National")
zenora_mask = (df["bank_name"] == "Zenora")

print("\nLarge bank comparison (All intents):")
print(f"  Tarang National: {(df.loc[tarang_mask, 'status'] == 'FAILED').mean() * 100:.2f}%")
print(f"  Zenora:          {(df.loc[zenora_mask, 'status'] == 'FAILED').mean() * 100:.2f}%")
print(f"  Other Large:     {(df.loc[other_large_mask, 'status'] == 'FAILED').mean() * 100:.2f}%")

fast_net_mask = df["network_type"].isin(["WiFi", "5G", "4G"])
print("\nLarge bank comparison (Fast network only: WiFi, 5G, 4G):")
print(f"  Tarang National: {(df.loc[tarang_mask & fast_net_mask, 'status'] == 'FAILED').mean() * 100:.2f}%")
print(f"  Zenora:          {(df.loc[zenora_mask & fast_net_mask, 'status'] == 'FAILED').mean() * 100:.2f}%")
print(f"  Other Large:     {(df.loc[other_large_mask & fast_net_mask, 'status'] == 'FAILED').mean() * 100:.2f}%")

print("\n=== 4. Bank-Family Failure Rate (Peak vs Other Hours) ===")
small_mask = (df["size_tier"] == "Small")
large_mask = (df["size_tier"] == "Large")
peak_mask = df["initiated_at"].dt.hour.isin(PEAK_HOURS)

small_peak_bfail = (df.loc[small_mask & peak_mask, "error_family"] == "bank").mean() * 100
small_other_bfail = (df.loc[small_mask & ~peak_mask, "error_family"] == "bank").mean() * 100
large_peak_bfail = (df.loc[large_mask & peak_mask, "error_family"] == "bank").mean() * 100
large_other_bfail = (df.loc[large_mask & ~peak_mask, "error_family"] == "bank").mean() * 100

print(f"Small banks - Peak (20-21h): {small_peak_bfail:.2f}%, Other hours: {small_other_bfail:.2f}%")
print(f"Large banks - Peak (20-21h): {large_peak_bfail:.2f}%, Other hours: {large_other_bfail:.2f}%")

print("\n=== 5. Network-Family Failure Rate (3G/2G vs WiFi/5G) ===")
slow_net = df["network_type"].isin(["3G", "2G"])
fast_net = df["network_type"].isin(["WiFi", "5G"])
slow_net_rate = (df.loc[slow_net, "error_family"] == "network").mean() * 100
fast_net_rate = (df.loc[fast_net, "error_family"] == "network").mean() * 100
ratio_net = slow_net_rate / fast_net_rate if fast_net_rate > 0 else 0
print(f"3G + 2G combined:   {slow_net_rate:.2f}%")
print(f"WiFi + 5G combined: {fast_net_rate:.2f}%")
print(f"Ratio (Slow / Fast): {ratio_net:.2f}x")

print("\n=== 6. Failure Rate by Device Type ===")
dev_fail = df.groupby("device_type")["status"].apply(lambda s: (s == "FAILED").mean() * 100)
for d_type, r_val in dev_fail.items():
    print(f"  {d_type:10s}: {r_val:.2f}%")

print("\n=== 7. Failure Rate by True Segment ===")
seg_fail = df.groupby("true_segment")["status"].apply(lambda s: (s == "FAILED").mean() * 100)
for s_name, r_val in seg_fail.items():
    print(f"  {s_name:16s}: {r_val:.2f}%")
fp_cfail = (df.loc[df["true_segment"] == "Failure-prone", "error_family"] == "customer").mean() * 100
rel_cfail = (df.loc[df["true_segment"] == "Reliable", "error_family"] == "customer").mean() * 100
print(f"Customer-family failure rate -> Failure-prone: {fp_cfail:.2f}%, Reliable: {rel_cfail:.2f}%")

print("\n=== 8. Outage Bank (Kestrel Commercial) Checks ===")
outage_bank_mask = (df["bank_name"] == OUTAGE_BANK)
inside_outage = outage_bank_mask & outage_mask
outside_outage = outage_bank_mask & ~outage_mask
in_count = inside_outage.sum()
out_count = outside_outage.sum()
in_fail = (df.loc[inside_outage, "status"] == "FAILED").mean() * 100 if in_count > 0 else 0
out_fail = (df.loc[outside_outage, "status"] == "FAILED").mean() * 100 if out_count > 0 else 0
print(f"Inside outage windows:  {in_fail:.2f}% (intents: {in_count})")
print(f"Outside outage windows: {out_fail:.2f}% (intents: {out_count})")

print("\n=== 9. Deploy PSP (Clearwave) Checks ===")
psp_dep_mask = (df["psp_id"] == deploy_psp_id)
inside_dep = psp_dep_mask & deploy_mask
outside_dep = psp_dep_mask & ~deploy_mask
in_psp01_share = (df.loc[inside_dep, "error_code"] == "PSP_01").mean() * 100 if inside_dep.sum() > 0 else 0
out_psp01_share = (df.loc[outside_dep, "error_code"] == "PSP_01").mean() * 100 if outside_dep.sum() > 0 else 0
print(f"Inside deploy window (3-16 Aug) PSP_01 share: {in_psp01_share:.2f}%")
print(f"Outside deploy window PSP_01 share:           {out_psp01_share:.2f}%")

print("\n=== 10. Limits & Risk Family Failures ===")
lim01_cnt = (df["error_code"] == "LIM_01").sum()
lim02_cnt = (df["error_code"] == "LIM_02").sum()
lim03_cnt = (df["error_code"] == "LIM_03").sum()
print(f"LIM_01 count: {lim01_cnt}")
print(f"LIM_02 count: {lim02_cnt}")
print(f"LIM_03 count: {lim03_cnt}")

high_amt_mask = (df["amount"] > 10000)
high_amt_rfail = (df.loc[high_amt_mask, "error_family"] == "risk").mean() * 100
low_amt_rfail = (df.loc[~high_amt_mask, "error_family"] == "risk").mean() * 100
print(f"Risk-family failure rate (Amount > 10,000):  {high_amt_rfail:.3f}%")
print(f"Risk-family failure rate (Amount <= 10,000): {low_amt_rfail:.3f}%")

print("\n=== 11. Failure Concentration (Top 8 Banks) ===")
top8_banks = df.loc[df["status"] == "FAILED", "bank_name"].value_counts().head(8).index
fail_share_top8 = df.loc[df["status"] == "FAILED", "bank_name"].isin(top8_banks).mean() * 100
vol_share_top8 = df["bank_name"].isin(top8_banks).mean() * 100
print(f"Top 8 banks by failures: {', '.join(top8_banks)}")
print(f"Share of all failures:   {fail_share_top8:.2f}%")
print(f"Share of total volume:   {vol_share_top8:.2f}%")

print("\nFailures generated OK")
