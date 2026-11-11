import os
import sys
import tempfile

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import scipy.stats as stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import adjusted_rand_score
import dotenv
import sqlalchemy

# Do NOT read truth.customer_truth until SECTION 5.

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv.load_dotenv(os.path.join(PROJECT_DIR, ".env"))

user = os.getenv("DB_USER", "postgres")
pwd = os.getenv("DB_PASSWORD", "123456")
host = os.getenv("DB_HOST", "localhost")
port = os.getenv("DB_PORT", "5432")
db = os.getenv("DB_NAME", "paymentiq")

engine = sqlalchemy.create_engine(f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}")

figures_dir = os.path.join(PROJECT_DIR, "reports", "figures")
os.makedirs(figures_dir, exist_ok=True)

results_file = os.path.join(PROJECT_DIR, "reports", "phase5_results.txt")
with open(results_file, "w", encoding="utf-8") as f:
    pass

def out(text=""):
    print(text)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")

out("=== PHASE 5-2: RETRY TIMING, FUNNEL AND SEGMENTATION ANALYSIS ===")

# ==============================================================================
# SECTION 1: TIME TO RETRY
# ==============================================================================
out("\n" + "=" * 70)
out("SECTION 1: TIME TO RETRY (v_retry_gaps)")
out("=" * 70)

with engine.begin() as conn:
    conn.execute(sqlalchemy.text(
        "CREATE INDEX IF NOT EXISTS idx_ja_cust_gap ON journey_attempts (customer_id, payee_id, amount, s30b, initiated_at)"
    ))

df_gaps = pd.read_sql("SELECT transaction_id, error_code, initiated_at, gap_s, next_status FROM v_retry_gaps", engine)

n_gaps = len(df_gaps)
p25 = df_gaps["gap_s"].quantile(0.25)
median_gap = df_gaps["gap_s"].quantile(0.50)
p75 = df_gaps["gap_s"].quantile(0.75)
p90 = df_gaps["gap_s"].quantile(0.90)
p95 = df_gaps["gap_s"].quantile(0.95)
share_above_1800 = (df_gaps["gap_s"] > 1800).mean()
share_above_600 = (df_gaps["gap_s"] > 600).mean()

out(f"Number of retry gaps observed: {n_gaps}")
out(f"Gap (seconds) quantiles: P25 = {p25:.1f}s, Median = {median_gap:.1f}s, P75 = {p75:.1f}s, P90 = {p90:.1f}s, P95 = {p95:.1f}s")
out(f"Share of retry gaps > 1800s (30m): {share_above_1800:.4f} ({share_above_1800*100:.2f}%)")
out(f"Share of retry gaps > 600s (10m):  {share_above_600:.4f} ({share_above_600*100:.2f}%)")

top8_codes = df_gaps["error_code"].value_counts().head(8).index.tolist()
out("\nMedian retry gap by error code (8 most frequent codes):")
gap_by_code = (
    df_gaps[df_gaps["error_code"].isin(top8_codes)]
    .groupby("error_code")["gap_s"]
    .agg(count="count", median_gap_s="median")
    .loc[top8_codes]
)
out(gap_by_code.to_string())

out("\nMedian retry gap by next status:")
gap_by_status = (
    df_gaps.groupby("next_status")["gap_s"]
    .agg(count="count", median_gap_s="median")
)
out(gap_by_status.to_string())

# Histogram of log10(gap_s) with vertical line at log10(1800)
fig, ax = plt.subplots(figsize=(8, 5))
valid_gaps = df_gaps["gap_s"][df_gaps["gap_s"] > 0]
log_gaps = np.log10(valid_gaps)
ax.hist(log_gaps, bins=50, color="#2b5c8f", edgecolor="black", alpha=0.75)
line_val = np.log10(1800)
ax.axvline(line_val, color="red", linestyle="--", linewidth=2, label=f"30-min window limit: log10(1800) = {line_val:.2f}")
ax.set_title("Distribution of Retry Gaps (w30b Journeys)", fontsize=13, fontweight="bold")
ax.set_xlabel("log10(Retry Gap in Seconds)", fontsize=11)
ax.set_ylabel("Count of Retried Attempts", fontsize=11)
ax.legend(frameon=True)
ax.grid(True, linestyle=":", alpha=0.6)
plt.tight_layout()
fig_p5_gap = os.path.join(figures_dir, "p5_retry_gap.png")
plt.savefig(fig_p5_gap, dpi=150)
plt.close()
out(f"\nSaved retry gap plot to {fig_p5_gap}")

# ==============================================================================
# SECTION 2: FUNNEL (w30b journeys)
# ==============================================================================
out("\n" + "=" * 70)
out("SECTION 2: RECOVERY FUNNEL (w30b journeys)")
out("=" * 70)

sql_funnel = """
SELECT j.jkey, j.customer_id, j.n_attempts, j.first_error, j.any_success, f.retry_class
FROM journey_summary j
JOIN dim_failure_codes f ON f.error_code = j.first_error
WHERE j.variant = 'w30b'
  AND j.first_status = 'FAILED'
  AND j.first_error NOT IN ('CUS_03', 'TEC_01', 'RSK_01')
"""
df_funnel = pd.read_sql(sql_funnel, engine)

n_eligible = len(df_funnel)
n_retried = (df_funnel["n_attempts"] > 1).sum()
n_recovered = df_funnel["any_success"].sum()
n_retried_not_rec = ((df_funnel["n_attempts"] > 1) & (~df_funnel["any_success"])).sum()
n_never_retried = (df_funnel["n_attempts"] == 1).sum()

unrecovered_df = df_funnel[~df_funnel["any_success"]]
n_unrecovered = len(unrecovered_df)
n_never_retried_unrec = (unrecovered_df["n_attempts"] == 1).sum()
share_never_retried_unrec = 100.0 * n_never_retried_unrec / n_unrecovered if n_unrecovered > 0 else 0.0

out(f"Eligible failed journeys (first-attempt failure): {n_eligible}")
out(f"  - Retried (>1 attempt):                          {n_retried} ({100.0 * n_retried / n_eligible:.2f}%)")
out(f"  - Recovered (any attempt succeeded):             {n_recovered} ({100.0 * n_recovered / n_eligible:.2f}%)")
out(f"  - Retried but not recovered:                     {n_retried_not_rec} ({100.0 * n_retried_not_rec / n_eligible:.2f}%)")
out(f"  - Never retried (abandoned immediately):         {n_never_retried} ({100.0 * n_never_retried / n_eligible:.2f}%)")
out(f"\nShare of unrecovered journeys that were NEVER retried: {share_never_retried_unrec:.2f}% ({n_never_retried_unrec} / {n_unrecovered})")

out("\nFunnel split by retry class of the first error:")
funnel_by_class = (
    df_funnel.groupby("retry_class")
    .agg(
        eligible=("jkey", "count"),
        retried=("n_attempts", lambda x: (x > 1).sum()),
        recovered=("any_success", "sum")
    )
)
funnel_by_class["retried_pct"] = (100.0 * funnel_by_class["retried"] / funnel_by_class["eligible"]).round(2)
funnel_by_class["recovered_pct"] = (100.0 * funnel_by_class["recovered"] / funnel_by_class["eligible"]).round(2)
out(funnel_by_class[["eligible", "retried_pct", "recovered_pct"]].to_string())

# ==============================================================================
# SECTION 3: CUSTOMER FEATURES
# ==============================================================================
out("\n" + "=" * 70)
out("SECTION 3: CUSTOMER FEATURES")
out("=" * 70)

df_cust = pd.read_sql("SELECT * FROM customer_features", engine)
n_total_cust = len(df_cust)

kept = df_cust[df_cust["journeys"] >= 5].copy()
n_kept = len(kept)
out(f"Total customers in features table: {n_total_cust}")
out(f"Kept customers with journeys >= 5: {n_kept} ({100.0 * n_kept / n_total_cust:.2f}%)")

kept["failure_rate"] = kept["failed_first"] / kept["journeys"]

overall_retry_rate = kept["retried"].sum() / kept["failed_first"].sum()
overall_retry_success = kept["retried_recovered"].sum() / kept["retried"].sum()
out(f"Overall retry rate (among failed):    {overall_retry_rate:.4f} ({overall_retry_rate*100:.2f}%)")
out(f"Overall retry success (among retry): {overall_retry_success:.4f} ({overall_retry_success*100:.2f}%)")

kept["retry_rate"] = np.where(kept["failed_first"] == 0, np.nan, kept["retried"] / kept["failed_first"])
kept["retry_rate"] = kept["retry_rate"].fillna(overall_retry_rate)

kept["retry_success"] = np.where(kept["retried"] == 0, np.nan, kept["retried_recovered"] / kept["retried"])
kept["retry_success"] = kept["retry_success"].fillna(overall_retry_success)

kept["log_avg_amount"] = np.log(np.maximum(kept["avg_amount"], 1.0))
kept["log_journeys"] = np.log(kept["journeys"])

feature_cols = ["failure_rate", "retry_rate", "retry_success", "log_avg_amount", "log_journeys"]
out("\nSummary statistics of derived customer features (kept customers):")
out(kept[feature_cols].describe().to_string())

# ==============================================================================
# SECTION 4: SEGMENTATION (BLIND)
# ==============================================================================
out("\n" + "=" * 70)
out("SECTION 4: BLIND SEGMENTATION (RULES & K-MEANS)")
out("=" * 70)

# (a) Rules
q_amt_88 = kept["avg_amount"].quantile(0.88)
q_fail_85 = kept["failure_rate"].quantile(0.85)
q_retry_20 = kept["retry_rate"].quantile(0.20)
q_retry_75 = kept["retry_rate"].quantile(0.75)

out(f"Rule thresholds: avg_amount Top 12% = {q_amt_88:.2f}, failure_rate Top 15% = {q_fail_85:.4f}, retry_rate Bottom 20% = {q_retry_20:.4f}, retry_rate Top 25% = {q_retry_75:.4f}")

def assign_rule(row):
    if row["avg_amount"] >= q_amt_88:
        return "High-value"
    elif row["failure_rate"] >= q_fail_85 and row["failed_first"] >= 3:
        return "Failure-prone"
    elif row["failed_first"] >= 3 and row["retry_rate"] <= q_retry_20:
        return "Abandoning"
    elif row["failed_first"] >= 3 and row["retry_rate"] >= q_retry_75:
        return "Retry-dependent"
    else:
        return "Reliable"

kept["rule_segment"] = kept.apply(assign_rule, axis=1)

out("\nRule-based Segment Counts:")
rule_counts = kept["rule_segment"].value_counts()
for seg, count in rule_counts.items():
    out(f"  {seg:<16}: {count:>6} ({100.0 * count / n_kept:5.2f}%)")

# (b) KMeans
scaler = StandardScaler()
X_scaled = scaler.fit_transform(kept[feature_cols])

kmeans = KMeans(n_clusters=5, n_init=20, random_state=42)
kept["kmeans_cluster"] = kmeans.fit_predict(X_scaled)

out("\nK-Means Cluster Sizes (k=5):")
cluster_counts = kept["kmeans_cluster"].value_counts().sort_index()
for cl, count in cluster_counts.items():
    out(f"  Cluster {cl}: {count:>6} ({100.0 * count / n_kept:5.2f}%)")

out("\nMean raw feature values per K-Means cluster:")
raw_feature_means = kept.groupby("kmeans_cluster")[feature_cols].mean()
out(raw_feature_means.to_string())

# ==============================================================================
# SECTION 5: SCORING (READ TRUTH)
# ==============================================================================
out("\n" + "=" * 70)
out("SECTION 5: SCORING AGAINST TRUTH (customer_truth)")
out("=" * 70)

df_truth = pd.read_sql("SELECT customer_id, true_segment FROM truth.customer_truth", engine)
merged = kept.merge(df_truth, on="customer_id")

out(f"Merged kept customers with truth: {len(merged)}")

out("\nCrosstab: True Segment (rows) vs Rule Segment (columns):")
ct_rules = pd.crosstab(merged["true_segment"], merged["rule_segment"])
out(ct_rules.to_string())

# Overall agreement
common_labels = ["Abandoning", "Failure-prone", "High-value", "Reliable", "Retry-dependent"]
agreement = (merged["true_segment"] == merged["rule_segment"]).mean()
out(f"\nOverall Agreement (Rule == True): {agreement:.4f} ({agreement * 100:.2f}%)")

out("\nPer-True-Segment Recall (Rules):")
recalls = {}
for seg in common_labels:
    sub = merged[merged["true_segment"] == seg]
    rec = (sub["rule_segment"] == seg).mean()
    recalls[seg] = rec
    out(f"  {seg:<16}: recall = {rec:.4f} ({rec * 100:.2f}%) [True N = {len(sub)}]")

ari_rules = adjusted_rand_score(merged["true_segment"], merged["rule_segment"])
ari_kmeans = adjusted_rand_score(merged["true_segment"], merged["kmeans_cluster"])
out(f"\nAdjusted Rand Index (Rules):   {ari_rules:.4f}")
out(f"Adjusted Rand Index (K-Means): {ari_kmeans:.4f}")

out("\nCrosstab: True Segment (rows) vs K-Means Cluster (columns):")
ct_kmeans = pd.crosstab(merged["true_segment"], merged["kmeans_cluster"])
out(ct_kmeans.to_string())

out("\nMean Features by TRUE Segment vs Planted Multipliers:")
true_stats = merged.groupby("true_segment").agg(
    failure_rate=("failure_rate", "mean"),
    retry_rate=("retry_rate", "mean"),
    retry_success=("retry_success", "mean"),
    avg_amount=("avg_amount", "mean"),
    count=("customer_id", "count")
)

planted_info = {
    "Reliable": "Baseline",
    "High-value": "avg_amount 2.5x",
    "Abandoning": "retry_rate 0.3x",
    "Retry-dependent": "retry_rate 1.4x",
    "Failure-prone": "customer-failure +0.5 log-odds, retry_succ 0.8x"
}
true_stats["planted_multiplier"] = true_stats.index.map(planted_info)
out(true_stats[["count", "failure_rate", "retry_rate", "retry_success", "avg_amount", "planted_multiplier"]].to_string())

# Scatter plot of failure_rate vs retry_rate colored by true segment
fig, ax = plt.subplots(figsize=(9, 6))
palette = {
    "Reliable": "#4a7bb0",
    "High-value": "#e69f00",
    "Abandoning": "#d55e00",
    "Retry-dependent": "#009e73",
    "Failure-prone": "#cc79a7"
}

# Subsample or jitter if large, but 20k with alpha 0.4 works well
for seg, col in palette.items():
    sub = merged[merged["true_segment"] == seg]
    ax.scatter(sub["failure_rate"], sub["retry_rate"], c=col, label=seg, alpha=0.35, s=16, edgecolors="none")

ax.set_title("Customer Segments: Failure Rate vs Retry Rate (True Segments)", fontsize=13, fontweight="bold")
ax.set_xlabel("First-Attempt Failure Rate", fontsize=11)
ax.set_ylabel("Retry Rate (upon Failure)", fontsize=11)
ax.legend(frameon=True, loc="upper right")
ax.grid(True, linestyle=":", alpha=0.5)
plt.tight_layout()
fig_p5_seg = os.path.join(figures_dir, "p5_segments.png")
plt.savefig(fig_p5_seg, dpi=150)
plt.close()
out(f"\nSaved segment scatter plot to {fig_p5_seg}")

# Plain sentence on recall
well_rec = [seg for seg, r in recalls.items() if r >= 0.5]
poor_rec = [seg for seg, r in recalls.items() if r < 0.5]
out(f"\nReliable ({recalls['Reliable']*100:.1f}%) and High-value ({recalls['High-value']*100:.1f}%) were recovered reasonably well, whereas Failure-prone ({recalls['Failure-prone']*100:.1f}%), Retry-dependent ({recalls['Retry-dependent']*100:.1f}%), and Abandoning ({recalls['Abandoning']*100:.1f}%) were recovered poorly because low failure counts per customer leave behavioral failure and retry rates noisy.")

out("\nPhase 5-2 analysis OK")
