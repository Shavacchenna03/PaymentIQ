import os
import sys
import numpy as np
import pandas as pd

raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# 1. Load files
dq_truth = pd.read_csv(os.path.join(raw_dir, "dq_truth.csv"), keep_default_na=False)

stg_txns = pd.read_csv(
    os.path.join(raw_dir, "stg_transactions.csv"),
    parse_dates=["initiated_at", "completed_at"],
    keep_default_na=False
)
# Take first occurrence of each transaction_id in staging
stg_first = stg_txns.drop_duplicates(subset=["transaction_id"], keep="first").copy()

clean_attempts = pd.read_csv(
    os.path.join(raw_dir, "attempts_all.csv"),
    parse_dates=["initiated_at", "completed_at"],
    keep_default_na=False
)
clean_attempts["error_code"] = clean_attempts["error_code"].replace("", np.nan)
clean_attempts["latency_ms"] = pd.to_numeric(clean_attempts["latency_ms"].replace("", np.nan), errors="coerce").astype("Int64")
clean_attempts["completed_at"] = pd.to_datetime(clean_attempts["completed_at"].replace("", np.nan))

# 2. Rows of dq_truth with MISSING_LATENCY
dq_lat = dq_truth[dq_truth["issue_type"] == "MISSING_LATENCY"].copy()
dq_lat["true_latency"] = pd.to_numeric(dq_lat["true_value"])

# Merge with staging rows on transaction_id
merged = dq_lat.merge(
    stg_first[["transaction_id", "initiated_at", "completed_at", "psp_id", "status", "error_code"]],
    on="transaction_id",
    how="inner"
)

# Also merge clean attempts to get clean status and error_code
clean_info = clean_attempts[["transaction_id", "status", "error_code"]].rename(
    columns={"status": "clean_status", "error_code": "clean_error_code"}
)
merged = merged.merge(clean_info, on="transaction_id", how="inner")

# 3. Compute diff_ms and err
merged["diff_ms"] = (merged["completed_at"] - merged["initiated_at"]).dt.total_seconds() * 1000.0
merged["err"] = merged["true_latency"] - (merged["diff_ms"] + 500.0)
merged["abs_err"] = np.abs(merged["err"])

# 4. Print results
print(f"Number of MISSING_LATENCY rows: {len(merged)}")

print("\n--- 10 rows with largest absolute err ---")
top10 = merged.sort_values(by="abs_err", ascending=False).head(10)
cols_to_show = ["transaction_id", "true_latency", "diff_ms", "err", "clean_status", "clean_error_code", "psp_id"]
print(top10[cols_to_show].to_string(index=False))

print("\n--- Distribution of err in bins ---")
bins = [-np.inf, -1000, -500, 0, 500, 1000, np.inf]
labels = ["below -1000", "-1000 to -500", "-500 to 0", "0 to 500", "500 to 1000", "above 1000"]
binned = pd.cut(merged["err"], bins=bins, labels=labels, right=False)
bin_counts = binned.value_counts().reindex(labels)
for lbl, cnt in bin_counts.items():
    print(f"  {lbl:<15}: {cnt:>5}")

ge_120k = (merged["true_latency"] >= 120000).sum()
print(f"\nNumber of rows with true_latency >= 120,000 ms: {ge_120k}")

# 5. ALL non-PENDING rows in clean attempts_all.csv with latency_ms present
clean_eligible = clean_attempts[
    (clean_attempts["status"] != "PENDING") & clean_attempts["latency_ms"].notna()
].copy()

dur_clean = (clean_eligible["completed_at"] - clean_eligible["initiated_at"]).dt.total_seconds() * 1000.0
clean_diff = clean_eligible["latency_ms"].astype(float) - dur_clean

med_diff = clean_diff.median()
max_diff = clean_diff.max()
share_gt_1000 = (clean_eligible["latency_ms"].astype(float) > (dur_clean + 1000.0)).mean() * 100.0

print("\n--- Clean attempts (all non-PENDING rows with latency_ms present) ---")
print(f"Eligible rows count:                                {len(clean_eligible):,}")
print(f"Median of (latency_ms - (completed_at - initiated_at)): {med_diff:.2f} ms")
print(f"Maximum of (latency_ms - (completed_at - initiated_at)): {max_diff:.2f} ms")
print(f"Share of rows where latency_ms > duration + 1000 ms:    {share_gt_1000:.4f}%")

print("\nDiagnosis done")

