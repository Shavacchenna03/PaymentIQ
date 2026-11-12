import os
import sys
import tempfile
import math

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
from scipy.stats import norm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import dotenv
import sqlalchemy

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv.load_dotenv(os.path.join(PROJECT_DIR, ".env"))

user = os.getenv("DB_USER", os.getenv("PGUSER", "postgres"))
pwd = os.getenv("DB_PASSWORD", os.getenv("PGPASSWORD", "123456"))
host = os.getenv("DB_HOST", os.getenv("PGHOST", "localhost"))
port = os.getenv("DB_PORT", os.getenv("PGPORT", "5432"))
db = os.getenv("DB_NAME", os.getenv("PGDATABASE", "paymentiq"))

engine = sqlalchemy.create_engine(f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}")

figures_dir = os.path.join(PROJECT_DIR, "reports", "figures")
os.makedirs(figures_dir, exist_ok=True)

results_file = os.path.join(PROJECT_DIR, "reports", "phase8_power.txt")
with open(results_file, "w", encoding="utf-8") as f:
    pass

def out(text=""):
    print(text)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")

out("=== PHASE 8-1: POWER ANALYSIS AND EXPERIMENT PLANNING ===")

# LOAD
load_sql = """
SELECT customer_id, jkey, first_time, any_success, n_attempts 
FROM value_journeys 
WHERE eligible
"""
with engine.connect() as conn:
    df_raw = pd.read_sql(load_sql, conn)
    dup_df = pd.read_sql("SELECT DISTINCT jkey FROM v_dup_detect", conn)

# Keep each customer's earliest journey (by first_time, then jkey)
pop_df = df_raw.sort_values(['customer_id', 'first_time', 'jkey']).groupby('customer_id').first().reset_index()

n_cust = len(pop_df)
baseline_rec = pop_df['any_success'].mean()
baseline_retry = (pop_df['n_attempts'] > 1).mean()

out(f"Experiment Population (Customers): {n_cust}")
out(f"Baseline Recovery Rate: {baseline_rec * 100:.2f}%")
out(f"Baseline Retry Rate: {baseline_retry * 100:.2f}%")

# DUPLICATE BASELINE
dup_jkeys = set(dup_df['jkey'])
pop_df['is_dup'] = pop_df['jkey'].isin(dup_jkeys)
dup_count = pop_df['is_dup'].sum()
dup_rate = pop_df['is_dup'].mean()

out(f"\nDuplicate Baseline Count: {dup_count}")
out(f"Duplicate Baseline Rate: {dup_rate * 100:.3f}% ({dup_rate:.6f})")
out("Note: This duplicate baseline is a detector-based proxy (about 83 percent precision against hidden truth).")

# HELPERS
def n_per_arm(p1, p2, alpha=0.05, power=0.8):
    z_alpha = norm.ppf(1.0 - alpha / 2.0)
    z_power = norm.ppf(power)
    denom = (p2 - p1) ** 2
    num = (z_alpha + z_power) ** 2 * (p1 * (1.0 - p1) + p2 * (1.0 - p2))
    return math.ceil(num / denom)

def mde(p1, n, alpha=0.05, power=0.8):
    lo = 1e-6
    hi = 0.5
    for _ in range(60):
        mid = (lo + hi) / 2.0
        p2 = p1 + mid
        if n_per_arm(p1, p2, alpha, power) > n:
            lo = mid
        else:
            hi = mid
    return hi

def n_noninf(p, margin, alpha=0.05, power=0.8):
    z_alpha = norm.ppf(1.0 - alpha)
    z_power = norm.ppf(power)
    denom = margin ** 2
    num = (z_alpha + z_power) ** 2 * 2.0 * p * (1.0 - p)
    return math.ceil(num / denom)

# SECTION 1 (primary)
out("\n--- SECTION 1: PRIMARY OUTCOME POWER ANALYSIS ---")
p1 = baseline_rec
power_rows = []
for eff in [1, 2, 3, 4, 5]:
    eff_prop = eff / 100.0
    for pw in [0.8, 0.9]:
        n_arm = n_per_arm(p1, p1 + eff_prop, alpha=0.05, power=pw)
        power_rows.append({
            'effect_pp': eff,
            'power': pw,
            'n_per_arm': n_arm,
            'n_total': 2 * n_arm
        })

df_power = pd.DataFrame(power_rows)
out(df_power.to_string(index=False))

power_csv_path = os.path.join(PROJECT_DIR, "reports", "phase8_power.csv")
df_power.to_csv(power_csv_path, index=False)

n_avail = n_cust // 2
out(f"\nAvailable per-arm sample: {n_avail} (Total population: {n_cust})")

detectable_08 = [r['effect_pp'] for r in power_rows if r['power'] == 0.8 and r['n_per_arm'] <= n_avail]
out(f"Effects detectable at power 0.8 with available sample size: +{detectable_08} percentage points")

# SECTION 2 (MDE curve)
out("\n--- SECTION 2: MINIMUM DETECTABLE EFFECT (MDE) CURVE ---")
sample_sizes = [500, 1000, 2000, 3000, 4000, 5000, 6000, 7000]
mde_vals = []
for n in sample_sizes:
    val_mde = mde(p1, n, alpha=0.05, power=0.8)
    mde_vals.append(val_mde * 100.0)
    out(f"  n = {n:4d}: MDE = {val_mde * 100.0:.2f} percentage points")

mde_avail = mde(p1, n_avail, alpha=0.05, power=0.8) * 100.0
out(f"Available n = {n_avail}: MDE = {mde_avail:.2f} percentage points")

# Plot 1: MDE Curve
plt.figure(figsize=(7, 5))
plt.plot(sample_sizes, mde_vals, marker='o', color='#1f77b4', linewidth=2, label='MDE (Power = 0.8)')
plt.axvline(x=n_avail, color='#d62728', linestyle='--', linewidth=1.5, label=f'Available n = {n_avail} (MDE = {mde_avail:.2f} pp)')
plt.title('Minimum Detectable Effect (MDE) Curve (Alpha = 0.05, Power = 0.8)')
plt.xlabel('Per-Arm Sample Size (n)')
plt.ylabel('Minimum Detectable Effect (percentage points)')
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(figures_dir, 'p8_mde_curve.png'), dpi=150)
plt.close()

# Plot 2: Sample Size vs Effect Size by Power
plt.figure(figsize=(7, 5))
eff_range = np.linspace(1.0, 5.0, 50)
n_08 = [n_per_arm(p1, p1 + e/100.0, alpha=0.05, power=0.8) for e in eff_range]
n_09 = [n_per_arm(p1, p1 + e/100.0, alpha=0.05, power=0.9) for e in eff_range]

plt.plot(eff_range, n_08, color='#1f77b4', linewidth=2, label='Power = 0.8')
plt.plot(eff_range, n_09, color='#ff7f0e', linewidth=2, label='Power = 0.9')
plt.axhline(y=n_avail, color='#d62728', linestyle='--', linewidth=1.5, label=f'Available n = {n_avail}')
plt.title('Required Sample Size per Arm by Effect Size and Power (Alpha = 0.05)')
plt.xlabel('Effect Size (percentage points)')
plt.ylabel('Required Sample Size per Arm (n)')
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(figures_dir, 'p8_sample_size.png'), dpi=150)
plt.close()

# SECTION 3 (guardrail)
out("\n--- SECTION 3: GUARDRAIL NON-INFERIORITY POWER ---")
out(f"Duplicate baseline rate: {dup_rate * 100:.3f}% ({dup_rate:.6f})")

noninf_margins = [0.25, 0.5, 1.0]
for m_pp in noninf_margins:
    m = m_pp / 100.0
    n_ni = n_noninf(dup_rate, m, alpha=0.05, power=0.8)
    out(f"  Non-inferiority margin {m_pp:4.2f} pp: required n per arm = {n_ni:6d}")

n_05_margin = n_noninf(dup_rate, 0.5 / 100.0, alpha=0.05, power=0.8)
suffices_05 = n_avail >= n_05_margin
out(f"\nDoes available per-arm n ({n_avail}) suffice for the 0.5 pp margin? {'YES' if suffices_05 else 'NO'} (requires {n_05_margin})")

z_alpha_1s = norm.ppf(0.95)
z_beta = norm.ppf(0.8)
supported_margin_pp = (z_alpha_1s + z_beta) * math.sqrt(2.0 * dup_rate * (1.0 - dup_rate) / n_avail) * 100.0
out(f"Minimum non-inferiority margin supported by available sample ({n_avail}) at power 0.8: {supported_margin_pp:.3f} percentage points")

out("If the guardrail is underpowered, a non-significant result does not show duplicates are safe.")

out("\nPhase 8-1 analysis OK")
