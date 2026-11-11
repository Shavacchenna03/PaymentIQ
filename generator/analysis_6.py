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

results_file = os.path.join(PROJECT_DIR, "reports", "phase6_results.txt")
with open(results_file, "w", encoding="utf-8") as f:
    pass

def out(text=""):
    print(text)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")

rng = np.random.default_rng(6)

out("=== PHASE 6-2: VALUE SCENARIO MODEL ===")

# --- LOAD ---
query = """
SELECT jkey, amount, any_success, first_error, retry_class, size_tier
FROM value_journeys
WHERE eligible
"""
df = pd.read_sql(query, engine)
n_rows = len(df)
out(f"\nLoaded eligible value journeys: {n_rows}")

# --- POOLS ---
is_limit = df["first_error"].str.startswith("LIM")
is_addr = df["retry_class"].isin(["Safe retry", "Verify status first", "Customer action"]) & (~is_limit)

df["pool"] = "other"
df.loc[is_limit, "pool"] = "limit"
df.loc[is_addr, "pool"] = "addr"

df["unrec"] = ~df["any_success"]

# --- BASELINE ---
out("\n--- BASELINE POOL SUMMARY ---")
pool_names = ["addr", "limit", "other"]
pool_rows = []

for p in pool_names:
    sub = df[df["pool"] == p]
    u = sub[sub["unrec"]]
    journeys_cnt = len(sub)
    unrec_cnt = len(u)
    unrec_lakh = u["amount"].sum() / 100000.0
    mean_unrec_amt = u["amount"].mean() if unrec_cnt > 0 else 0.0
    rec_rate_count = sub["any_success"].mean() * 100.0 if journeys_cnt > 0 else 0.0
    pool_rows.append({
        "pool": p,
        "journeys": journeys_cnt,
        "unrecovered_journeys": unrec_cnt,
        "unrecovered_lakh": unrec_lakh,
        "mean_unrec_amount": mean_unrec_amt,
        "recovery_rate_count_pct": rec_rate_count
    })

# Total row
u_tot = df[df["unrec"]]
tot_journeys = len(df)
tot_unrec_cnt = len(u_tot)
tot_unrec_lakh = u_tot["amount"].sum() / 100000.0
tot_mean_unrec = u_tot["amount"].mean() if tot_unrec_cnt > 0 else 0.0
tot_rec_rate = df["any_success"].mean() * 100.0

pool_rows.append({
    "pool": "total",
    "journeys": tot_journeys,
    "unrecovered_journeys": tot_unrec_cnt,
    "unrecovered_lakh": tot_unrec_lakh,
    "mean_unrec_amount": tot_mean_unrec,
    "recovery_rate_count_pct": tot_rec_rate
})

df_baseline = pd.DataFrame(pool_rows)
out(df_baseline.to_string(index=False))

# Share of addr unrecovered value that comes from BNK_03
addr_unrec_df = df[(df["pool"] == "addr") & (df["unrec"])]
bnk03_unrec_lakh = addr_unrec_df[addr_unrec_df["first_error"] == "BNK_03"]["amount"].sum() / 100000.0
addr_tot_unrec_lakh = addr_unrec_df["amount"].sum() / 100000.0
bnk03_share_pct = (bnk03_unrec_lakh / addr_tot_unrec_lakh * 100.0) if addr_tot_unrec_lakh > 0 else 0.0
out(f"\nShare of retry-addressable unrecovered value from BNK_03 (Insufficient funds): {bnk03_unrec_lakh:.2f} lakh / {addr_tot_unrec_lakh:.2f} lakh ({bnk03_share_pct:.2f}%)")

# --- SCENARIOS (HYPOTHETICAL) ---
# Point estimates:
N_addr = len(df[df["pool"] == "addr"])
mean_unrec_amount_addr = addr_unrec_df["amount"].mean()
addr_unrec_val_lakh = addr_tot_unrec_lakh

limit_unrec_df = df[(df["pool"] == "limit") & (df["unrec"])]
limit_unrec_val_lakh = limit_unrec_df["amount"].sum() / 100000.0

scenarios = [
    {
        "scenario": "+2 pp recovery (retry-addressable)",
        "family": "Retry-addressable",
        "assumption": "+2 pp recovery gain on addressable pool",
        "type": "addr",
        "param": 2.0
    },
    {
        "scenario": "+5 pp recovery (retry-addressable)",
        "family": "Retry-addressable",
        "assumption": "+5 pp recovery gain on addressable pool",
        "type": "addr",
        "param": 5.0
    },
    {
        "scenario": "+10 pp recovery (retry-addressable)",
        "family": "Retry-addressable",
        "assumption": "+10 pp recovery gain on addressable pool",
        "type": "addr",
        "param": 10.0
    },
    {
        "scenario": "10% limit recovery (alternative rail)",
        "family": "Limit",
        "assumption": "10% of limit unrecovered value captured",
        "type": "limit",
        "param": 10.0
    },
    {
        "scenario": "25% limit recovery (alternative rail)",
        "family": "Limit",
        "assumption": "25% of limit unrecovered value captured",
        "type": "limit",
        "param": 25.0
    }
]

for sc in scenarios:
    if sc["type"] == "addr":
        g = sc["param"]
        gain = (g / 100.0) * N_addr * mean_unrec_amount_addr / 100000.0
        sc["gain_lakh"] = min(gain, addr_unrec_val_lakh)
    else:
        s = sc["param"]
        sc["gain_lakh"] = (s / 100.0) * limit_unrec_val_lakh

# --- BOOTSTRAP (1000 resamples) ---
out("\n--- RUNNING 1000 BOOTSTRAP RESAMPLES ---")
n_boot = 1000

# Pre-extract numpy arrays for fast resampling
amounts = df["amount"].to_numpy()
is_addr_arr = (df["pool"] == "addr").to_numpy()
is_limit_arr = (df["pool"] == "limit").to_numpy()
is_other_arr = (df["pool"] == "other").to_numpy()
is_unrec_arr = df["unrec"].to_numpy()

boot_addr_unrec = np.empty(n_boot)
boot_limit_unrec = np.empty(n_boot)
boot_other_unrec = np.empty(n_boot)
boot_total_unrec = np.empty(n_boot)

boot_scenario_gains = {sc["scenario"]: np.empty(n_boot) for sc in scenarios}

for b in range(n_boot):
    idx = rng.integers(0, n_rows, size=n_rows)
    b_amt = amounts[idx]
    b_addr = is_addr_arr[idx]
    b_limit = is_limit_arr[idx]
    b_other = is_other_arr[idx]
    b_unrec = is_unrec_arr[idx]
    
    # Pool unrecovered lakh
    b_addr_unrec_mask = b_addr & b_unrec
    b_limit_unrec_mask = b_limit & b_unrec
    b_other_unrec_mask = b_other & b_unrec
    
    b_addr_u_lakh = b_amt[b_addr_unrec_mask].sum() / 100000.0
    b_limit_u_lakh = b_amt[b_limit_unrec_mask].sum() / 100000.0
    b_other_u_lakh = b_amt[b_other_unrec_mask].sum() / 100000.0
    b_tot_u_lakh = b_addr_u_lakh + b_limit_u_lakh + b_other_u_lakh
    
    boot_addr_unrec[b] = b_addr_u_lakh
    boot_limit_unrec[b] = b_limit_u_lakh
    boot_other_unrec[b] = b_other_u_lakh
    boot_total_unrec[b] = b_tot_u_lakh
    
    # Scenario gains
    b_N_addr = b_addr.sum()
    b_mean_unrec_addr = b_amt[b_addr_unrec_mask].mean() if b_addr_unrec_mask.any() else 0.0
    
    for sc in scenarios:
        if sc["type"] == "addr":
            g = sc["param"]
            g_lakh = min((g / 100.0) * b_N_addr * b_mean_unrec_addr / 100000.0, b_addr_u_lakh)
            boot_scenario_gains[sc["scenario"]][b] = g_lakh
        else:
            s = sc["param"]
            s_lakh = (s / 100.0) * b_limit_u_lakh
            boot_scenario_gains[sc["scenario"]][b] = s_lakh

# 2.5th and 97.5th percentiles for pools
pool_ci = {
    "addr": (np.percentile(boot_addr_unrec, 2.5), np.percentile(boot_addr_unrec, 97.5)),
    "limit": (np.percentile(boot_limit_unrec, 2.5), np.percentile(boot_limit_unrec, 97.5)),
    "other": (np.percentile(boot_other_unrec, 2.5), np.percentile(boot_other_unrec, 97.5)),
    "total": (np.percentile(boot_total_unrec, 2.5), np.percentile(boot_total_unrec, 97.5))
}

out("\nBootstrap 95% Confidence Intervals for Unrecovered Value (Lakh):")
for p, (lo, hi) in pool_ci.items():
    out(f"  {p:<6}: 95% CI = [{lo:.2f}, {hi:.2f}] lakh")

# Attach CIs to pools dataframe
df_pools_export = df_baseline[["pool", "journeys", "unrecovered_journeys", "unrecovered_lakh"]].copy()
df_pools_export["ci_low"] = df_pools_export["pool"].map(lambda p: round(pool_ci[p][0], 2))
df_pools_export["ci_high"] = df_pools_export["pool"].map(lambda p: round(pool_ci[p][1], 2))
df_pools_export["unrecovered_lakh"] = df_pools_export["unrecovered_lakh"].round(2)

pools_csv = os.path.join(PROJECT_DIR, "reports", "phase6_pools.csv")
df_pools_export.to_csv(pools_csv, index=False)
out(f"\nSaved pools table to {pools_csv}")

# Scenario CIs and revenues
scenario_rows = []
for sc in scenarios:
    s_name = sc["scenario"]
    ci_lo = float(np.percentile(boot_scenario_gains[s_name], 2.5))
    ci_hi = float(np.percentile(boot_scenario_gains[s_name], 97.5))
    gain = sc["gain_lakh"]
    
    # Revenue at 0.3%, 0.5%, 1.0%
    # Revenue = gain_lakh * 100000 * (take_rate_pct / 100)
    rev_03 = gain * 100000.0 * 0.003
    rev_05 = gain * 100000.0 * 0.005
    rev_10 = gain * 100000.0 * 0.010
    
    scenario_rows.append({
        "scenario": s_name,
        "family": sc["family"],
        "assumption": sc["assumption"],
        "gain_lakh": round(gain, 2),
        "ci_low": round(ci_lo, 2),
        "ci_high": round(ci_hi, 2),
        "revenue_rs_at_0.3pct": round(rev_03, 1),
        "revenue_rs_at_0.5pct": round(rev_05, 1),
        "revenue_rs_at_1.0pct": round(rev_10, 1)
    })

df_scenarios = pd.DataFrame(scenario_rows)
scenarios_csv = os.path.join(PROJECT_DIR, "reports", "phase6_scenarios.csv")
df_scenarios.to_csv(scenarios_csv, index=False)
out(f"Saved scenarios table to {scenarios_csv}")

# --- FIGURES ---
# 1. reports/figures/p6_unrecovered_by_pool.png
fig, ax = plt.subplots(figsize=(8, 5))
plot_pools = ["addr", "limit", "other"]
pool_disp_names = ["Retry-addressable", "Policy Limit", "Other (Escalate)"]
pool_vals = [df_pools_export.loc[df_pools_export["pool"] == p, "unrecovered_lakh"].values[0] for p in plot_pools]
pool_err_low = [pool_vals[i] - pool_ci[plot_pools[i]][0] for i in range(len(plot_pools))]
pool_err_high = [pool_ci[plot_pools[i]][1] - pool_vals[i] for i in range(len(plot_pools))]
yerr_pools = [pool_err_low, pool_err_high]

colors = ["#2b5c8f", "#d95f02", "#7570b3"]
bars = ax.bar(pool_disp_names, pool_vals, yerr=yerr_pools, capsize=6, color=colors, alpha=0.85, edgecolor="black")

for bar, val in zip(bars, pool_vals):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 5, f"{val:.1f}L", ha="center", va="bottom", fontweight="bold", fontsize=10)

ax.set_ylabel("Unrecovered Value (Lakh ₹)", fontsize=11)
ax.set_xlabel("Failure Pool", fontsize=11)
ax.set_title("Unrecovered Value by Pool with 95% Bootstrap CI", fontsize=12, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.6, axis="y")
plt.tight_layout()
fig_pool_path = os.path.join(figures_dir, "p6_unrecovered_by_pool.png")
plt.savefig(fig_pool_path, dpi=150)
plt.close()
out(f"Saved pool bar chart to {fig_pool_path}")

# 2. reports/figures/p6_scenarios.png
fig, ax = plt.subplots(figsize=(10, 5.5))
sc_names = [sc["scenario"] for sc in scenarios]
sc_gains = [sc["gain_lakh"] for sc in scenario_rows]
sc_err_low = [sc_gains[i] - scenario_rows[i]["ci_low"] for i in range(len(scenarios))]
sc_err_high = [scenario_rows[i]["ci_high"] - sc_gains[i] for i in range(len(scenarios))]
yerr_sc = [sc_err_low, sc_err_high]

sc_colors = ["#2b5c8f" if sc["family"] == "Retry-addressable" else "#d95f02" for sc in scenarios]

x_pos = np.arange(len(sc_names))
bars = ax.bar(x_pos, sc_gains, yerr=yerr_sc, capsize=6, color=sc_colors, alpha=0.85, edgecolor="black")

for bar, val in zip(bars, sc_gains):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.6, f"{val:.1f}L", ha="center", va="bottom", fontweight="bold", fontsize=10)

# Custom legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor="#2b5c8f", edgecolor="black", label="Retry-addressable (+pp gain)"),
    Patch(facecolor="#d95f02", edgecolor="black", label="Limit alternative rail (% capture)")
]
ax.legend(handles=legend_elements, loc="upper left", frameon=True)

ax.set_xticks(x_pos)
ax.set_xticklabels([
    "+2 pp\nRetry",
    "+5 pp\nRetry",
    "+10 pp\nRetry",
    "10% Limit\nAlt Rail",
    "25% Limit\nAlt Rail"
], fontsize=10)
ax.set_ylabel("Potential Value Gain (Lakh ₹)", fontsize=11)
ax.set_title("HYPOTHETICAL Recovery Scenarios: Recoverable Value (95% Bootstrap CI)", fontsize=12, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.6, axis="y")
plt.tight_layout()
fig_sc_path = os.path.join(figures_dir, "p6_scenarios.png")
plt.savefig(fig_sc_path, dpi=150)
plt.close()
out(f"Saved scenario chart to {fig_sc_path}")

# --- PRINT FINAL OUTPUTS ---
out("\n" + "=" * 80)
out("POOLS TABLE (with 95% Bootstrap CI):")
out("=" * 80)
out(df_pools_export.to_string(index=False))

out("\n" + "=" * 80)
out("HYPOTHETICAL SCENARIOS TABLE (with Bootstrap CI & Revenue Sensitivity):")
out("=" * 80)
out(df_scenarios.to_string(index=False))

out("\nAll scenario values are hypothetical, not achieved results; take rates are assumptions.")
out("\nPhase 6-2 analysis OK")
