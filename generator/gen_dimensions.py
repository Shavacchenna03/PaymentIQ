import os
import sys
from datetime import date, timedelta
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add generator directory to sys.path to safely import config
sys.path.insert(0, os.path.dirname(__file__))
from config import *

# a. Create rng
rng = np.random.default_rng(SEED)

# b. Build dim_banks
dim_banks = pd.DataFrame(BANKS, columns=["bank_id", "bank_name", "bank_type", "size_tier"])

# c. Build dim_psp (columns: psp_id, psp_name, provider_type; drop the share)
dim_psp = pd.DataFrame(
    [(p[0], p[1], p[2]) for p in PSPS],
    columns=["psp_id", "psp_name", "provider_type"]
)

# d. Build dim_failure_codes
dim_failure_codes = pd.DataFrame(
    FAILURE_CODES,
    columns=["error_code", "category", "description", "retry_class"]
)

# e. Build dim_customers
def make_exact_array(share_dict, n_total, rng_inst):
    arr = []
    for k, share in share_dict.items():
        count = int(round(n_total * share))
        arr.extend([k] * count)
    assert len(arr) == n_total, f"Expected {n_total}, got {len(arr)}"
    arr = np.array(arr)
    rng_inst.shuffle(arr)
    return arr

# signup_date
n_old = int(round(N_CUSTOMERS * SIGNUP_SHARE_OLD))
n_new = N_CUSTOMERS - n_old

old_start = date.fromisoformat(SIGNUP_OLD_START)
old_end = date.fromisoformat(SIGNUP_OLD_END)
old_days = (old_end - old_start).days + 1
old_rand_days = rng.integers(0, old_days, size=n_old)
old_dates = [old_start + timedelta(days=int(d)) for d in old_rand_days]

new_start = date.fromisoformat(SIGNUP_NEW_START)
new_end = date.fromisoformat(SIGNUP_NEW_END)
new_days = (new_end - new_start).days + 1
new_rand_days = rng.integers(0, new_days, size=n_new)
new_dates = [new_start + timedelta(days=int(d)) for d in new_rand_days]

signup_dates = np.array(old_dates + new_dates, dtype=object)
rng.shuffle(signup_dates)

city_tiers = make_exact_array(CITY_TIER_SHARE, N_CUSTOMERS, rng)
devices = make_exact_array(DEVICE_SHARE, N_CUSTOMERS, rng)
channels = make_exact_array(CHANNEL_SHARE, N_CUSTOMERS, rng)

dim_customers = pd.DataFrame({
    "customer_id": np.arange(1, N_CUSTOMERS + 1),
    "signup_date": signup_dates,
    "city_tier": city_tiers,
    "primary_device": devices,
    "acquisition_channel": channels
})

# f. Build truth.customer_truth (customer_id, true_segment)
customer_truth = pd.DataFrame({
    "customer_id": np.arange(1, N_CUSTOMERS + 1),
    "true_segment": make_exact_array(SEGMENT_SHARE, N_CUSTOMERS, rng)
})

# g. Assertions
assert len(dim_banks) == 40, f"Expected 40 banks, got {len(dim_banks)}"
assert len(dim_psp) == 7, f"Expected 7 PSPs, got {len(dim_psp)}"
assert len(dim_failure_codes) == 28, f"Expected 28 failure codes, got {len(dim_failure_codes)}"
assert len(dim_customers) == 30000, f"Expected 30000 customers, got {len(dim_customers)}"
assert len(customer_truth) == 30000, f"Expected 30000 truth rows, got {len(customer_truth)}"
assert np.isclose(sum(p[3] for p in PSPS), 1.0), "PSP volume shares must sum to 1.0"
assert np.isclose(sum(TIER_VOLUME_SHARE.values()), 1.0), "Tier volume shares must sum to 1.0"

# h. Connect to paymentiq with SQLAlchemy and load tables
load_dotenv()
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "paymentiq")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")

database_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(database_url)

with engine.begin() as conn:
    conn.execute(text("TRUNCATE dim_banks, dim_psp, dim_failure_codes, dim_customers, truth.customer_truth CASCADE;"))

dim_banks.to_sql("dim_banks", con=engine, schema="public", if_exists="append", index=False, method="multi", chunksize=5000)
dim_psp.to_sql("dim_psp", con=engine, schema="public", if_exists="append", index=False, method="multi", chunksize=5000)
dim_failure_codes.to_sql("dim_failure_codes", con=engine, schema="public", if_exists="append", index=False, method="multi", chunksize=5000)
dim_customers.to_sql("dim_customers", con=engine, schema="public", if_exists="append", index=False, method="multi", chunksize=5000)
customer_truth.to_sql("customer_truth", con=engine, schema="truth", if_exists="append", index=False, method="multi", chunksize=5000)

# i. Save each table as CSV in data/raw/
raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(raw_dir, exist_ok=True)

dim_banks.to_csv(os.path.join(raw_dir, "dim_banks.csv"), index=False)
dim_psp.to_csv(os.path.join(raw_dir, "dim_psp.csv"), index=False)
dim_failure_codes.to_csv(os.path.join(raw_dir, "dim_failure_codes.csv"), index=False)
dim_customers.to_csv(os.path.join(raw_dir, "dim_customers.csv"), index=False)
customer_truth.to_csv(os.path.join(raw_dir, "customer_truth.csv"), index=False)

# j. Prints
print("=== Table Row Counts ===")
print(f"dim_banks: {len(dim_banks)}")
print(f"dim_psp: {len(dim_psp)}")
print(f"dim_failure_codes: {len(dim_failure_codes)}")
print(f"dim_customers: {len(dim_customers)}")
print(f"truth.customer_truth: {len(customer_truth)}")

print("\n=== Value Counts: size_tier (dim_banks) ===")
print(dim_banks["size_tier"].value_counts().to_string())

print("\n=== Value Counts: city_tier (dim_customers) ===")
print(dim_customers["city_tier"].value_counts().to_string())

print("\n=== Value Counts: primary_device (dim_customers) ===")
print(dim_customers["primary_device"].value_counts().to_string())

print("\n=== Value Counts: acquisition_channel (dim_customers) ===")
print(dim_customers["acquisition_channel"].value_counts().to_string())

print("\n=== Value Counts: true_segment (truth.customer_truth) ===")
print(customer_truth["true_segment"].value_counts().to_string())

cutoff = date.fromisoformat("2026-03-31")
on_or_before = (dim_customers["signup_date"] <= cutoff).sum()
after = (dim_customers["signup_date"] > cutoff).sum()
print("\n=== Signup Date Breakdown ===")
print(f"Signed up on or before 2026-03-31: {on_or_before}")
print(f"Signed up after 2026-03-31: {after}")

print("\nDimensions loaded OK")

