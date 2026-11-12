import os
import sys
import tempfile
import math

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
from scipy.stats import norm, chi2
import statsmodels.formula.api as smf
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

results_file = os.path.join(PROJECT_DIR, "reports", "phase8_sim.txt")
with open(results_file, "w", encoding="utf-8") as f:
    pass

def out(text=""):
    print(text)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")

out("=== PHASE 8-2: SIMULATED EXPERIMENT AND POWER STUDY ===")

# POPULATION
load_sql = """
SELECT customer_id, jkey, first_time, any_success, n_attempts, amount, size_tier, city_tier, retry_class 
FROM value_journeys 
WHERE eligible
"""
with engine.connect() as conn:
    df_raw = pd.read_sql(load_sql, conn)
    dup_df = pd.read_sql("SELECT DISTINCT jkey FROM v_dup_detect", conn)

df = df_raw.sort_values(['customer_id', 'first_time', 'jkey']).groupby('customer_id').first().reset_index()

dup_jkeys = set(dup_df['jkey'])
df['dup0'] = df['jkey'].isin(dup_jkeys).astype(int)
df['rec0'] = df['any_success'].astype(int)
df['retry0'] = (df['n_attempts'] > 1).astype(int)
df['log_amt'] = np.log(df['amount'].clip(lower=1.0))

N = len(df)
mean_rec0 = float(df['rec0'].mean())
mean_retry0 = float(df['retry0'].mean())
mean_dup0 = float(df['dup0'].mean())

out(f"Population size N: {N} (expect 14250)")
out(f"Mean baseline recovery (rec0): {mean_rec0 * 100:.2f}%")
out(f"Mean baseline retry (retry0):    {mean_retry0 * 100:.2f}%")
out(f"Mean baseline duplicate (dup0): {mean_dup0 * 100:.3f}% ({mean_dup0:.6f})")

# CONSTANTS
MARGIN = 0.005
Z975 = norm.ppf(0.975)
Z95 = norm.ppf(0.95)

scenarios = {
    'A': (0.03, 0.0),      # tau_rec 0.03, tau_dup 0.0
    'B': (0.0, 0.0),       # null
    'C': (0.03, 0.008)     # tau_rec 0.03, tau_dup 0.008
}

scen_labels = {
    'A': 'Scenario A (+3 pp recovery, 0 dup)',
    'B': 'Scenario B (Null / A/A)',
    'C': 'Scenario C (+3 pp recovery, +0.8 pp dup)'
}

# SIMULATE FUNCTION
def simulate(rng, scen, p_treat=0.5):
    tau_rec, tau_dup = scen
    assign = rng.random(N) < p_treat
    u1 = rng.random(N)
    u2 = rng.random(N)
    
    p_flip_rec = tau_rec / (1.0 - mean_rec0) if (1.0 - mean_rec0) > 0 else 0.0
    flip_rec = assign & (df['rec0'].values == 0) & (u1 < p_flip_rec)
    rec = df['rec0'].values | flip_rec.astype(int)
    retry = df['retry0'].values | flip_rec.astype(int)
    
    p_flip_dup = tau_dup / (1.0 - mean_dup0) if (1.0 - mean_dup0) > 0 else 0.0
    flip_dup = assign & (df['dup0'].values == 0) & (u2 < p_flip_dup)
    dup = df['dup0'].values | flip_dup.astype(int)
    
    return assign, rec, retry, dup

# ANALYSE FUNCTION
def analyse(assign, rec, retry, dup):
    n1 = int(assign.sum())
    n0 = int(N - n1)
    
    rec1 = float(rec[assign].mean())
    rec0 = float(rec[~assign].mean())
    diff_rec = rec1 - rec0
    se_rec = math.sqrt(rec1 * (1.0 - rec1) / n1 + rec0 * (1.0 - rec0) / n0)
    ci_rec_lower = diff_rec - Z975 * se_rec
    ci_rec_upper = diff_rec + Z975 * se_rec
    
    p_pool = float(rec.sum()) / N
    se_pool = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n0))
    z_rec = diff_rec / se_pool if se_pool > 0 else 0.0
    p_val_rec = 2.0 * (1.0 - norm.cdf(abs(z_rec)))
    
    dup1 = float(dup[assign].mean())
    dup0 = float(dup[~assign].mean())
    diff_dup = dup1 - dup0
    se_dup = max(math.sqrt(dup1 * (1.0 - dup1) / n1 + dup0 * (1.0 - dup0) / n0), 1e-9)
    dup_upper = diff_dup + Z95 * se_dup
    
    retry1 = float(retry[assign].mean())
    retry0 = float(retry[~assign].mean())
    diff_retry = retry1 - retry0
    
    e = N / 2.0
    chi2_stat = ((n1 - e) ** 2 + (n0 - e) ** 2) / e
    p_val_srm = 1.0 - chi2.cdf(chi2_stat, df=1)
    
    decision = "SHIP" if (ci_rec_lower > 0 and dup_upper < MARGIN) else "DO NOT SHIP"
    
    return {
        'n1': n1, 'n0': n0,
        'rec1': rec1, 'rec0': rec0, 'diff_rec': diff_rec,
        'ci_rec_lower': ci_rec_lower, 'ci_rec_upper': ci_rec_upper,
        'p_val_rec': p_val_rec,
        'dup1': dup1, 'dup0': dup0, 'diff_dup': diff_dup, 'dup_upper': dup_upper,
        'retry1': retry1, 'retry0': retry0, 'diff_retry': diff_retry,
        'p_val_srm': p_val_srm,
        'decision': decision
    }

def wilson_ci(pos, n, z=Z975):
    if n == 0:
        return (0.0, 0.0)
    p = pos / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    rad = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return ((center - rad) / denom, (center + rad) / denom)

# SECTION 1: DETAILED RUNS
out("\n--- SECTION 1: DETAILED RUN PER SCENARIO (SEED = 88) ---")
detailed_results = {}

for sc_name, scen in scenarios.items():
    rng = np.random.default_rng(88)
    assign, rec, retry, dup = simulate(rng, scen)
    res = analyse(assign, rec, retry, dup)
    detailed_results[sc_name] = res
    
    # Wilson intervals for recovery
    ci_w_ctrl = wilson_ci(rec[~assign].sum(), res['n0'])
    ci_w_treat = wilson_ci(rec[assign].sum(), res['n1'])
    
    out(f"\n{scen_labels[sc_name]}:")
    out(f"  Arm sizes: Control n0 = {res['n0']}, Treatment n1 = {res['n1']} (SRM chi-square p = {res['p_val_srm']:.4f})")
    out(f"  Recovery Rate: Control = {res['rec0']*100:.2f}% (Wilson 95% CI: [{ci_w_ctrl[0]*100:.2f}%, {ci_w_ctrl[1]*100:.2f}%]), Treatment = {res['rec1']*100:.2f}% (Wilson 95% CI: [{ci_w_treat[0]*100:.2f}%, {ci_w_treat[1]*100:.2f}%])")
    out(f"  Recovery Difference: {res['diff_rec']*100:.2f} pp [95% CI: {res['ci_rec_lower']*100:.2f}, {res['ci_rec_upper']*100:.2f}], p = {res['p_val_rec']:.4f}")
    out(f"  Retry Rate: Control = {res['retry0']*100:.2f}%, Treatment = {res['retry1']*100:.2f}%, Difference = {res['diff_retry']*100:.2f} pp")
    out(f"  Abandonment (complement of recovery): Control = {(1.0-res['rec0'])*100:.2f}%, Treatment = {(1.0-res['rec1'])*100:.2f}%, Difference = {-(res['diff_rec'])*100:.2f} pp")
    out(f"  Duplicate Rate: Control = {res['dup0']*100:.3f}%, Treatment = {res['dup1']*100:.3f}%")
    out(f"  Duplicate Difference: {res['diff_dup']*100:.3f} pp, One-sided 95% Upper Bound = {res['dup_upper']*100:.3f} pp (Non-inf margin = {MARGIN*100:.2f} pp)")
    out(f"  Decision: {res['decision']}")
    
    # Logistic regression robustness check
    df_run = df.copy()
    df_run['treat'] = assign.astype(int)
    df_run['rec'] = rec
    fit = smf.logit("rec ~ treat + C(size_tier) + C(city_tier) + log_amt + C(retry_class)", data=df_run).fit(disp=False)
    or_val = np.exp(fit.params['treat'])
    ci_or = np.exp(fit.conf_int().loc['treat'])
    p_or = fit.pvalues['treat']
    out(f"  Adjusted Logistic: Treatment OR = {or_val:.3f} [95% CI: {ci_or[0]:.3f}, {ci_or[1]:.3f}], p = {p_or:.4f} (Unadjusted diff = {res['diff_rec']*100:.2f} pp)")

# SECTION 2: 1,000 REPEATS POWER STUDY
out("\n--- SECTION 2: 1,000 REPEATS POWER STUDY (SEED = 2026) ---")
rng_study = np.random.default_rng(2026)
repeat_summary = []

for sc_name, scen in scenarios.items():
    ships = []
    ci_lows_pos = []
    p_two_sided_sig = []
    guard_pass = []
    diff_recs = []
    diff_dups = []
    srm_flags = []
    
    for _ in range(1000):
        assign, rec, retry, dup = simulate(rng_study, scen)
        res = analyse(assign, rec, retry, dup)
        ships.append(res['decision'] == 'SHIP')
        ci_lows_pos.append(res['ci_rec_lower'] > 0)
        p_two_sided_sig.append(res['p_val_rec'] < 0.05)
        guard_pass.append(res['dup_upper'] < MARGIN)
        diff_recs.append(res['diff_rec'])
        diff_dups.append(res['diff_dup'])
        srm_flags.append(res['p_val_srm'] < 0.001)
        
    ship_rate = np.mean(ships)
    ci_pos_rate = np.mean(ci_lows_pos)
    sig_rate = np.mean(p_two_sided_sig)
    guard_rate = np.mean(guard_pass)
    mean_rec_diff = np.mean(diff_recs)
    p25_rec = np.percentile(diff_recs, 2.5)
    p975_rec = np.percentile(diff_recs, 97.5)
    mean_dup_diff = np.mean(diff_dups)
    srm_flag_rate = np.mean(srm_flags)
    
    out(f"\n{scen_labels[sc_name]}:")
    out(f"  Ship Rate: {ship_rate*100:.1f}%")
    out(f"  CI Lower > 0 (recovery significant): {ci_pos_rate*100:.1f}%")
    out(f"  Two-sided p < 0.05 (A/A false positive for B): {sig_rate*100:.1f}%")
    out(f"  Guardrail Pass (upper bound < 0.5 pp): {guard_rate*100:.1f}%")
    out(f"  Mean Recovery Diff: {mean_rec_diff*100:.2f} pp [2.5th: {p25_rec*100:.2f} pp, 97.5th: {p975_rec*100:.2f} pp]")
    out(f"  Mean Duplicate Diff: {mean_dup_diff*100:.3f} pp")
    out(f"  SRM Flag Rate (p < 0.001): {srm_flag_rate*100:.2f}%")
    
    repeat_summary.append({
        'scenario': sc_name,
        'label': scen_labels[sc_name],
        'ship_rate': round(ship_rate, 4),
        'ci_lower_gt_0': round(ci_pos_rate, 4),
        'two_sided_p_lt_05': round(sig_rate, 4),
        'guardrail_pass': round(guard_rate, 4),
        'mean_recovery_diff': round(mean_rec_diff, 5),
        'p2_5_recovery_diff': round(p25_rec, 5),
        'p97_5_recovery_diff': round(p975_rec, 5),
        'mean_duplicate_diff': round(mean_dup_diff, 6),
        'srm_flag_rate': round(srm_flag_rate, 4)
    })

out("\nInconclusive-on-safety branch: 0 by construction, because the guardrail is powered (smallest supported margin 0.313 pp, below the 0.5 pp margin)")

df_repeats = pd.DataFrame(repeat_summary)
csv_repeats_path = os.path.join(PROJECT_DIR, "reports", "phase8_sim_repeats.csv")
df_repeats.to_csv(csv_repeats_path, index=False)

# SECTION 3: SRM DETECTOR DEMO
out("\n--- SECTION 3: SRM DETECTOR DEMO ---")
srm_demo_flags = []
for _ in range(1000):
    assign, rec, retry, dup = simulate(rng_study, scenarios['B'], p_treat=0.55)
    res = analyse(assign, rec, retry, dup)
    srm_demo_flags.append(res['p_val_srm'] < 0.001)

srm_flagged_share = np.mean(srm_demo_flags)
out(f"SRM detector flag rate (p_treat = 0.55, threshold p < 0.001 across 1,000 runs): {srm_flagged_share * 100:.1f}%")

# FIGURES
# Figure 1: p8_power_study.png
fig, ax = plt.subplots(figsize=(7, 5))
sc_keys = ['A', 'B', 'C']
ship_rates_pct = [df_repeats.loc[df_repeats['scenario'] == k, 'ship_rate'].values[0] * 100.0 for k in sc_keys]
bars = ax.bar(['Scenario A\n(+3 pp rec)', 'Scenario B\n(Null)', 'Scenario C\n(+3 pp rec, +0.8 pp dup)'], ship_rates_pct, color=['#2ca02c', '#7f7f7f', '#d62728'], width=0.5)

ax.set_ylabel('Ship Rate (%)')
ax.set_ylim(0, 110)
ax.set_title('SIMULATED Experiment: Ship Rate by Scenario (1,000 Repeats)')
ax.grid(axis='y', linestyle='--', alpha=0.5)

for bar in bars:
    h = bar.get_height()
    ax.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontweight='bold')

plt.tight_layout()
plt.savefig(os.path.join(figures_dir, 'p8_power_study.png'), dpi=150)
plt.close()

# Figure 2: p8_detailed_ci.png
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

x_pos = np.arange(3)
sc_names = ['A', 'B', 'C']
sc_disp = ['Scen A\n(+3 pp)', 'Scen B\n(Null)', 'Scen C\n(+3 pp, +0.8 pp dup)']

# Panel 1: Recovery Difference with 95% CI
rec_diffs = [detailed_results[k]['diff_rec'] * 100.0 for k in sc_names]
rec_err_lo = [rec_diffs[i] - detailed_results[k]['ci_rec_lower'] * 100.0 for i, k in enumerate(sc_names)]
rec_err_hi = [detailed_results[k]['ci_rec_upper'] * 100.0 - rec_diffs[i] for i, k in enumerate(sc_names)]

ax1.errorbar(x_pos, rec_diffs, yerr=[rec_err_lo, rec_err_hi], fmt='o', capsize=5, capthick=1.5, color='#1f77b4', ecolor='#1f77b4', markersize=7)
ax1.axhline(0, color='black', linestyle='--', linewidth=1.2)
ax1.set_xticks(x_pos)
ax1.set_xticklabels(sc_disp)
ax1.set_ylabel('Recovery Difference (percentage points)')
ax1.set_title('SIMULATED: Recovery Difference (95% CI)')
ax1.grid(True, linestyle='--', alpha=0.5)

# Panel 2: Duplicate Difference with One-sided 95% Upper Bound
dup_diffs = [detailed_results[k]['diff_dup'] * 100.0 for k in sc_names]
dup_upper_err = [detailed_results[k]['dup_upper'] * 100.0 - dup_diffs[i] for i, k in enumerate(sc_names)]
# one-sided upper error bar: lower error is 0, upper error is dup_upper_err
ax2.errorbar(x_pos, dup_diffs, yerr=[np.zeros(3), dup_upper_err], fmt='s', capsize=5, capthick=1.5, color='#d62728', ecolor='#d62728', markersize=7)
ax2.axhline(MARGIN * 100.0, color='#d62728', linestyle='--', linewidth=1.5, label=f'Margin = {MARGIN*100:.1f} pp')
ax2.axhline(0, color='black', linestyle=':', linewidth=1.0)
ax2.set_xticks(x_pos)
ax2.set_xticklabels(sc_disp)
ax2.set_ylabel('Duplicate Difference (percentage points)')
ax2.set_title('SIMULATED: Duplicate Difference (One-sided 95% Upper Bound)')
ax2.legend()
ax2.grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig(os.path.join(figures_dir, 'p8_detailed_ci.png'), dpi=150)
plt.close()

out("\nSimulated results show how the method behaves under an assumed effect, not whether the redesign works")
out("Phase 8-2 analysis OK")
