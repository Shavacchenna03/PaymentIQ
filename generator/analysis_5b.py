import os
import sys
import tempfile

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import dotenv
import sqlalchemy

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

# 1. Load data
df_cohorts = pd.read_sql("SELECT * FROM v_cohorts ORDER BY cohort", engine)
df_activity = pd.read_sql("SELECT * FROM v_cohort_activity ORDER BY cohort, month", engine)

# 2. Save CSV
csv_path = os.path.join(PROJECT_DIR, "reports", "w3_cohort_table.csv")
df_cohorts.to_csv(csv_path, index=False)

# 3. Create markdown table
# Columns: cohort, customers, journeys_per_customer, first_failure_pct (ci_low to ci_high), retry_rate_pct, recovery_all_pct
# Determine pooled rate and overlap
total_failed = df_cohorts["failed_first"].sum()
total_journeys = df_cohorts["journeys"].sum()
pooled_rate = 100.0 * total_failed / total_journeys

min_row = df_cohorts.loc[df_cohorts["first_failure_pct"].idxmin()]
max_row = df_cohorts.loc[df_cohorts["first_failure_pct"].idxmax()]

all_overlap = True
for _, r in df_cohorts.iterrows():
    if not (r["ci_low"] <= pooled_rate <= r["ci_high"]):
        all_overlap = False

overlap_str = "every cohort's 95% Wilson confidence interval overlaps the pooled rate" if all_overlap else "not all cohort intervals overlap the pooled rate"

md_lines = [
    "| cohort | customers | journeys_per_customer | first_failure_pct (ci_low to ci_high) | retry_rate_pct | recovery_all_pct |",
    "|---|---|---|---|---|---|"
]

for _, r in df_cohorts.iterrows():
    c_ci = f"{r['first_failure_pct']:.2f} ({r['ci_low']:.2f} to {r['ci_high']:.2f})"
    md_lines.append(
        f"| {r['cohort']} | {int(r['customers'])} | {r['journeys_per_customer']:.2f} | {c_ci} | {r['retry_rate_pct']:.2f} | {r['recovery_all_pct']:.2f} |"
    )

summary_sentence = (
    f"\nFirst-attempt failure rate ranges from {min_row['first_failure_pct']:.2f}% ({min_row['cohort']}) "
    f"to {max_row['first_failure_pct']:.2f}% ({max_row['cohort']}), and {overlap_str} of {pooled_rate:.2f}%.\n"
)
md_lines.append(summary_sentence)

md_path = os.path.join(PROJECT_DIR, "reports", "w3_cohort_table.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

# 4. Generate Figure reports/figures/p5_cohorts.png
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

# Panel 1: first_failure_pct by cohort with Wilson error bars
cohort_labels = df_cohorts["cohort"].tolist()
rates = df_cohorts["first_failure_pct"].values
yerr_low = rates - df_cohorts["ci_low"].values
yerr_high = df_cohorts["ci_high"].values - rates
yerr = np.array([yerr_low, yerr_high])

x_pos = np.arange(len(cohort_labels))
ax1.errorbar(x_pos, rates, yerr=yerr, fmt='o', color="#1f77b4", ecolor="#d62728", elinewidth=2, capsize=4, markersize=6)
ax1.axhline(pooled_rate, color="gray", linestyle="--", alpha=0.7, label=f"Pooled rate: {pooled_rate:.2f}%")
ax1.set_xticks(x_pos)
ax1.set_xticklabels(cohort_labels, rotation=30, ha="right", fontsize=9)
ax1.set_ylabel("First-Attempt Failure Rate (%)", fontsize=11)
ax1.set_xlabel("Signup Cohort", fontsize=11)
ax1.set_title("First-Attempt Failure Rate by Cohort (95% Wilson CI)", fontsize=12, fontweight="bold")
ax1.grid(True, linestyle=":", alpha=0.6)
ax1.legend(loc="upper right")

# Panel 2: active_pct by month for new cohorts
unique_cohorts = df_activity["cohort"].unique()
month_order = sorted(df_activity["month"].unique())

for cohort in unique_cohorts:
    sub = df_activity[df_activity["cohort"] == cohort]
    ax2.plot(sub["month"], sub["active_pct"], marker="o", linewidth=2, label=cohort)

ax2.set_xlabel("Calendar Month", fontsize=11)
ax2.set_ylabel("Active Customers (%)", fontsize=11)
ax2.set_title("Monthly Activity Rate of New Cohorts", fontsize=12, fontweight="bold")
ax2.grid(True, linestyle=":", alpha=0.6)
ax2.legend(title="Cohort", loc="lower left", fontsize=9)
ax2.tick_params(axis="x", rotation=30)

plt.tight_layout()
fig_path = os.path.join(figures_dir, "p5_cohorts.png")
plt.savefig(fig_path, dpi=150)
plt.close()

# Print cohort table and OK
print("=== W3 COHORT TABLE ===")
print("\n".join(md_lines))
print("\nPhase 5-3 analysis OK")
