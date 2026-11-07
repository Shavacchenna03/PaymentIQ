import os
import sys
from datetime import date, timedelta
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# a. Imports & RNG
sys.path.insert(0, os.path.dirname(__file__))
from config import *

rng = np.random.default_rng(SEED + 1)

# b. Load database dimensions
load_dotenv()
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "paymentiq")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")

engine = create_engine(f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

dim_banks = pd.read_sql("SELECT * FROM dim_banks ORDER BY bank_id", engine)
dim_customers = pd.read_sql("SELECT * FROM dim_customers ORDER BY customer_id", engine)
customer_truth = pd.read_sql("SELECT * FROM truth.customer_truth ORDER BY customer_id", engine)
dim_psp = pd.read_sql("SELECT * FROM dim_psp ORDER BY psp_id", engine)

# c. DAY WEIGHTS
d_start = date.fromisoformat(START_DATE)
d_end = date.fromisoformat(END_DATE)
number_of_days = (d_end - d_start).days + 1
all_dates = [d_start + timedelta(days=i) for i in range(number_of_days)]

day_weights = []
for day_index, dt in enumerate(all_dates):
    growth = 1.0 + GROWTH_TOTAL * day_index / (number_of_days - 1)
    weekday = dt.weekday() # Monday=0
    weekday_w = WEEKDAY_WEIGHT[weekday]
    month_end_w = MONTH_END_BUMP if (dt.day >= 28 or dt.day <= 2) else 1.0
    day_weights.append(growth * weekday_w * month_end_w)

day_weights = np.array(day_weights, dtype=float)
day_probabilities = day_weights / day_weights.sum()
day_counts = rng.multinomial(N_BASE_INTENTS, day_probabilities)

# e. CUSTOMER activity & daily selection (done before d so intents are mapped to days & customers)
cust_segment_map = dict(zip(customer_truth["customer_id"], customer_truth["true_segment"]))
cust_segments = dim_customers["customer_id"].map(cust_segment_map).values

cust_base_act = rng.lognormal(0, ACTIVITY_SIGMA, size=len(dim_customers))
cust_seg_act = np.array([SEGMENT_ACTIVITY[s] for s in cust_segments])
cust_activity = cust_base_act * cust_seg_act

cust_signup_dates = pd.to_datetime(dim_customers["signup_date"]).dt.date.values
all_cust_ids = dim_customers["customer_id"].values.astype(int)

base_customer_ids = []
base_intent_dates = []

for day_index, dt in enumerate(all_dates):
    count = day_counts[day_index]
    if count == 0:
        continue
    candidates_mask = (cust_signup_dates <= dt)
    cand_ids = all_cust_ids[candidates_mask]
    cand_act = cust_activity[candidates_mask]
    cand_probs = cand_act / cand_act.sum()
    
    chosen = rng.choice(cand_ids, size=count, p=cand_probs)
    base_customer_ids.extend(chosen)
    base_intent_dates.extend([dt] * count)

base_customer_ids = np.array(base_customer_ids, dtype=int)

# d. HOUR
hour_probs = np.array(HOUR_WEIGHT, dtype=float) / sum(HOUR_WEIGHT)
base_hours = rng.choice(24, size=N_BASE_INTENTS, p=hour_probs)
base_minutes = rng.integers(0, 60, size=N_BASE_INTENTS)
base_seconds = rng.integers(0, 60, size=N_BASE_INTENTS)

base_initiated_at = (
    pd.to_datetime(base_intent_dates)
    + pd.to_timedelta(base_hours, unit="h")
    + pd.to_timedelta(base_minutes, unit="m")
    + pd.to_timedelta(base_seconds, unit="s")
)

# f. BANKS: primary and secondary banks per customer
tier_bank_counts = dim_banks["size_tier"].value_counts().to_dict()
bank_ids = dim_banks["bank_id"].values.astype(int)

rescaled_tilts = {}
for _, b in dim_banks.iterrows():
    b_id = int(b["bank_id"])
    b_name = b["bank_name"]
    b_tier = b["size_tier"]
    
    if b_name in CITY_TILT:
        raw = CITY_TILT[b_name].copy()
    elif b_tier == "Small":
        raw = CITY_TILT["_small_default"].copy()
    else:
        raw = {"Tier1": 1.0, "Tier2": 1.0, "Tier3": 1.0}
        
    s = sum(CITY_TIER_SHARE[t] * raw[t] for t in ["Tier1", "Tier2", "Tier3"])
    rescaled_tilts[b_id] = {t: raw[t] / s for t in ["Tier1", "Tier2", "Tier3"]}

city_tier_bank_weights = {}
for ct in ["Tier1", "Tier2", "Tier3"]:
    w = np.zeros(len(bank_ids), dtype=float)
    for idx, b_id in enumerate(bank_ids):
        tier = dim_banks.loc[dim_banks["bank_id"] == b_id, "size_tier"].values[0]
        base_w = TIER_VOLUME_SHARE[tier] / tier_bank_counts[tier]
        tilt = rescaled_tilts[b_id][ct]
        w[idx] = base_w * tilt
    w /= w.sum()
    city_tier_bank_weights[ct] = w

cust_primary_banks = np.empty(len(dim_customers), dtype=int)
cust_secondary_banks = np.empty(len(dim_customers), dtype=int)

for i, cust in dim_customers.iterrows():
    ct = cust["city_tier"]
    w = city_tier_bank_weights[ct].copy()
    p_bank = rng.choice(bank_ids, p=w)
    cust_primary_banks[i] = p_bank
    
    p_idx = np.where(bank_ids == p_bank)[0][0]
    w[p_idx] = 0.0
    w /= w.sum()
    s_bank = rng.choice(bank_ids, p=w)
    cust_secondary_banks[i] = s_bank

cust_primary_map = dict(zip(dim_customers["customer_id"], cust_primary_banks))
cust_secondary_map = dict(zip(dim_customers["customer_id"], cust_secondary_banks))

use_primary = rng.random(size=N_BASE_INTENTS) < PRIMARY_BANK_SHARE
primary_arr = np.array([cust_primary_map[c] for c in base_customer_ids])
secondary_arr = np.array([cust_secondary_map[c] for c in base_customer_ids])
base_bank_id = np.where(use_primary, primary_arr, secondary_arr)

# g. NETWORK
cust_city_map = dict(zip(dim_customers["customer_id"], dim_customers["city_tier"]))
base_city_tiers = np.array([cust_city_map[c] for c in base_customer_ids])

net_names = ["WiFi", "5G", "4G", "3G", "2G"]
base_network_type = np.empty(N_BASE_INTENTS, dtype=object)
for ct in ["Tier1", "Tier2", "Tier3"]:
    mask = (base_city_tiers == ct)
    n_ct = mask.sum()
    if n_ct > 0:
        p_net = [NETWORK_PROBS[ct][n] for n in net_names]
        base_network_type[mask] = rng.choice(net_names, size=n_ct, p=p_net)

# h. PAYEE
cat_names = list(PAYEE_CATEGORIES.keys())
cat_weights = [PAYEE_CATEGORIES[c][0] for c in cat_names]
cat_probs = np.array(cat_weights, dtype=float) / sum(cat_weights)
base_payee_category = rng.choice(cat_names, size=N_BASE_INTENTS, p=cat_probs)

base_payee_id = np.empty(N_BASE_INTENTS, dtype=int)
ranks = np.arange(1, PAYEES_PER_CATEGORY + 1)
zipf_p = (1.0 / ranks) / np.sum(1.0 / ranks)

for k, c in enumerate(cat_names):
    mask = (base_payee_category == c)
    n_cat = mask.sum()
    if n_cat > 0:
        cat_ids = np.arange(k * PAYEES_PER_CATEGORY + 1, (k + 1) * PAYEES_PER_CATEGORY + 1)
        base_payee_id[mask] = rng.choice(cat_ids, size=n_cat, p=zipf_p)

# i. AMOUNT
cat_median_map = {c: PAYEE_CATEGORIES[c][1] for c in cat_names}
cat_sigma_map = {c: PAYEE_CATEGORIES[c][2] for c in cat_names}

medians = np.array([cat_median_map[c] for c in base_payee_category], dtype=float)
sigmas = np.array([cat_sigma_map[c] for c in base_payee_category], dtype=float)

z = rng.standard_normal(size=N_BASE_INTENTS)
base_amount = medians * np.exp(sigmas * z)

base_segments = np.array([cust_segment_map[c] for c in base_customer_ids])
seg_mult = np.array([AMOUNT_SEGMENT_MULT[s] for s in base_segments], dtype=float)
base_amount *= seg_mult

zenora_id = dim_banks.loc[dim_banks["bank_name"] == "Zenora", "bank_id"].values[0]
zenora_mask = (base_bank_id == zenora_id)
base_amount = np.where(zenora_mask, base_amount * ZENORA_AMOUNT_FACTOR, base_amount)

base_amount = np.round(base_amount).astype(int)
base_amount = np.clip(base_amount, 1, 100000)

# j. PSP & DEVICE & CHANNEL
psp_ids = [p[0] for p in PSPS]
psp_shares = [p[3] for p in PSPS]
base_psp_id = rng.choice(psp_ids, size=N_BASE_INTENTS, p=psp_shares)

cust_device_map = dict(zip(dim_customers["customer_id"], dim_customers["primary_device"]))
base_device_type = np.array([cust_device_map[c] for c in base_customer_ids])

channel_names = list(CHANNEL_MIX.keys())
channel_probs = [CHANNEL_MIX[c] for c in channel_names]

non_web_mask = (base_device_type != "Web")
base_channel = np.empty(N_BASE_INTENTS, dtype=object)
base_channel[~non_web_mask] = "Web checkout"
if non_web_mask.sum() > 0:
    base_channel[non_web_mask] = rng.choice(channel_names, size=non_web_mask.sum(), p=channel_probs)

# k. REPEAT TRAP
cutoff_ts = pd.Timestamp("2026-09-30 23:00:00")
candidate_repeat_indices = np.where(base_initiated_at < cutoff_ts)[0]
chosen_repeat_indices = rng.choice(candidate_repeat_indices, size=N_REPEAT_INTENTS, replace=False)

repeat_customer_id = base_customer_ids[chosen_repeat_indices]
repeat_payee_id = base_payee_id[chosen_repeat_indices]
repeat_payee_category = base_payee_category[chosen_repeat_indices]
repeat_bank_id = base_bank_id[chosen_repeat_indices]
repeat_psp_id = base_psp_id[chosen_repeat_indices]
repeat_amount = base_amount[chosen_repeat_indices]
repeat_device_type = base_device_type[chosen_repeat_indices]
repeat_network_type = base_network_type[chosen_repeat_indices]
repeat_channel = base_channel[chosen_repeat_indices]

delta_minutes = rng.integers(5, 46, size=N_REPEAT_INTENTS)
delta_seconds = rng.integers(0, 60, size=N_REPEAT_INTENTS)

repeat_initiated_at = (
    base_initiated_at[chosen_repeat_indices]
    + pd.to_timedelta(delta_minutes, unit="m")
    + pd.to_timedelta(delta_seconds, unit="s")
)

base_temp_ids = np.arange(N_BASE_INTENTS)
repeat_of_temp_ids = base_temp_ids[chosen_repeat_indices]

# l. Combine and sort
base_df = pd.DataFrame({
    "temp_id": base_temp_ids,
    "customer_id": base_customer_ids,
    "payee_id": base_payee_id,
    "payee_category": base_payee_category,
    "bank_id": base_bank_id,
    "psp_id": base_psp_id,
    "amount": base_amount,
    "initiated_at": base_initiated_at,
    "device_type": base_device_type,
    "network_type": base_network_type,
    "channel": base_channel,
    "repeat_of_temp_id": -1,
})

repeat_df = pd.DataFrame({
    "temp_id": -1,
    "customer_id": repeat_customer_id,
    "payee_id": repeat_payee_id,
    "payee_category": repeat_payee_category,
    "bank_id": repeat_bank_id,
    "psp_id": repeat_psp_id,
    "amount": repeat_amount,
    "initiated_at": repeat_initiated_at,
    "device_type": repeat_device_type,
    "network_type": repeat_network_type,
    "channel": repeat_channel,
    "repeat_of_temp_id": repeat_of_temp_ids,
})

all_df = pd.concat([base_df, repeat_df], ignore_index=True)
all_df = all_df.sort_values("initiated_at", kind="mergesort").reset_index(drop=True)
all_df["intent_id"] = np.arange(1, len(all_df) + 1)

temp_to_final = dict(zip(all_df.loc[all_df["temp_id"] >= 0, "temp_id"], all_df.loc[all_df["temp_id"] >= 0, "intent_id"]))
all_df["repeat_of_intent_id"] = all_df["repeat_of_temp_id"].map(temp_to_final)
all_df["repeat_of_intent_id"] = all_df["repeat_of_intent_id"].astype("Int64")

# m. ASSERTS
assert len(all_df) == N_INTENTS, f"Expected {N_INTENTS}, got {len(all_df)}"
cust_signup_map = dict(zip(dim_customers["customer_id"], pd.to_datetime(dim_customers["signup_date"]).dt.date))
cust_signups = all_df["customer_id"].map(cust_signup_map)
assert (all_df["initiated_at"].dt.date >= cust_signups).all(), "Found initiated_at earlier than customer signup_date"
assert (all_df["initiated_at"] <= pd.Timestamp("2026-09-30 23:59:59")).all(), "Found initiated_at after 2026-09-30 23:59:59"
assert ((all_df["amount"] >= 1) & (all_df["amount"] <= 100000)).all(), "Amount out of range [1, 100000]"

# n. Save data/raw/intents.csv
cols = [
    "intent_id", "customer_id", "payee_id", "payee_category", "bank_id",
    "psp_id", "amount", "initiated_at", "device_type", "network_type",
    "channel", "repeat_of_intent_id"
]
out_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "intents.csv")
all_df[cols].to_csv(out_path, index=False)

# o. PRINT CHECKS
print("=== 1. Volume & Customer Counts ===")
print(f"Row count: {len(all_df)}")
print(f"Repeat count: {all_df['repeat_of_intent_id'].notna().sum()}")
print(f"Distinct customers with >= 1 intent: {all_df['customer_id'].nunique()}")

print("\n=== 2. Intents per Calendar Month & Ratio ===")
months = ["April", "May", "June", "July", "August", "September"]
month_counts = all_df["initiated_at"].dt.month_name().value_counts().reindex(months)
for m, c in month_counts.items():
    print(f"{m}: {c}")
ratio = month_counts["September"] / month_counts["April"]
print(f"September / April ratio: {ratio:.4f}")

print("\n=== 3. Intents per Weekday ===")
weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday_counts = all_df["initiated_at"].dt.day_name().value_counts().reindex(weekdays)
for wd, c in weekday_counts.items():
    print(f"{wd}: {c}")

print("\n=== 4. Share of Intents by Hour ===")
hours = all_df["initiated_at"].dt.hour
h_0_5_share = (hours.isin(range(0, 6))).mean() * 100
h_20_21_share = (hours.isin([20, 21])).mean() * 100
print(f"Hours 0-5 combined share: {h_0_5_share:.2f}%")
print(f"Hours 20-21 combined share: {h_20_21_share:.2f}%")

print("\n=== 5. Bank Tier Share of Intents (%) ===")
bank_tier_map = dict(zip(dim_banks["bank_id"], dim_banks["size_tier"]))
all_df["size_tier"] = all_df["bank_id"].map(bank_tier_map)
tier_shares = all_df["size_tier"].value_counts(normalize=True).reindex(["Large", "Medium", "Small"]) * 100
for t, s in tier_shares.items():
    print(f"{t}: {s:.2f}%")

print("\n=== 6. Tilts: Tarang National and Zenora Shares (%) ===")
bank_name_map = dict(zip(dim_banks["bank_id"], dim_banks["bank_name"]))
all_df["bank_name"] = all_df["bank_id"].map(bank_name_map)
all_df["city_tier"] = all_df["customer_id"].map(cust_city_map)

t3_mask = (all_df["city_tier"] == "Tier3")
t1_mask = (all_df["city_tier"] == "Tier1")

tarang_t3 = (all_df.loc[t3_mask, "bank_name"] == "Tarang National").mean() * 100
tarang_t1 = (all_df.loc[t1_mask, "bank_name"] == "Tarang National").mean() * 100
zenora_t1 = (all_df.loc[t1_mask, "bank_name"] == "Zenora").mean() * 100
zenora_t3 = (all_df.loc[t3_mask, "bank_name"] == "Zenora").mean() * 100

print(f"Tarang National share among Tier3 customers: {tarang_t3:.2f}%")
print(f"Tarang National share among Tier1 customers: {tarang_t1:.2f}%")
print(f"Zenora share among Tier1 customers: {zenora_t1:.2f}%")
print(f"Zenora share among Tier3 customers: {zenora_t3:.2f}%")

print("\n=== 7. Share of Intents Using Primary Bank (%) ===")
all_df["cust_primary_bank"] = all_df["customer_id"].map(cust_primary_map)
primary_share = (all_df["bank_id"] == all_df["cust_primary_bank"]).mean() * 100
print(f"Primary bank share: {primary_share:.2f}%")

print("\n=== 8. Network Share per City Tier (%) ===")
net_cross = pd.crosstab(all_df["city_tier"], all_df["network_type"], normalize="index")[["WiFi", "5G", "4G", "3G", "2G"]] * 100
print(net_cross.round(2).to_string())

print("\n=== 9. Median Amount Checks (INR) ===")
cat_medians = all_df.groupby("payee_category")["amount"].median()
print("Median amount per payee category:")
for cat, med in cat_medians.items():
    print(f"  {cat}: Rs {med:,.0f}")
zenora_med = all_df.loc[all_df["bank_name"] == "Zenora", "amount"].median()
other_med = all_df.loc[all_df["bank_name"] != "Zenora", "amount"].median()
print(f"Median amount - Zenora: Rs {zenora_med:,.0f}")
print(f"Median amount - All other banks: Rs {other_med:,.0f}")

print("\n=== 10. PSP Share of Intents (%) ===")
psp_name_map = dict(zip(dim_psp["psp_id"], dim_psp["psp_name"]))
all_df["psp_name"] = all_df["psp_id"].map(psp_name_map)
psp_shares = all_df["psp_name"].value_counts(normalize=True) * 100
for p_name, s in psp_shares.items():
    print(f"{p_name}: {s:.2f}%")

print("\n=== 11. Per-Customer Intent Count ===")
cust_counts_active = all_df["customer_id"].value_counts()
cust_counts_all = all_df["customer_id"].value_counts().reindex(np.arange(1, N_CUSTOMERS + 1), fill_value=0)
print(f"Active customers -> Min: {cust_counts_active.min()}, Median: {cust_counts_active.median():.0f}, Max: {cust_counts_active.max()}")
print(f"All 30,000 customers -> Min: {cust_counts_all.min()}, Median: {cust_counts_all.median():.0f}, Max: {cust_counts_all.max()}")

print("\nIntents generated OK")
