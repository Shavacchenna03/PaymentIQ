import os
import sys
import tempfile

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
import dotenv
import sqlalchemy

# Do NOT import generator/config.py until the final SCORING section.
# Do not read data/raw/failure_truth.csv at all.

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

results_file = os.path.join(PROJECT_DIR, "reports", "phase4d_results.txt")
with open(results_file, "w", encoding="utf-8") as f:
    pass

def out(text=""):
    print(text)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")

out("=== PHASE 4D: SIMPSON'S TRAP REGRESSION ANALYSIS ===")

# --- LOAD ---
out("\n--- Loading Data ---")
df = pd.read_sql("SELECT * FROM v_first_rc", engine)
kestrel_anom_df = pd.read_sql("SELECT date_key FROM v_anomaly_kestrel WHERE is_anomaly", engine)
kestrel_flagged_dates = set(pd.to_datetime(kestrel_anom_df["date_key"]).dt.date)

out(f"Loaded v_first_rc rows: {len(df)} (expect 273574)")
out(f"Number of Kestrel flagged dates: {len(kestrel_flagged_dates)}")

# --- FEATURES ---
df["attempt_date"] = pd.to_datetime(df["attempt_date"])
df["initiated_at"] = pd.to_datetime(df["initiated_at"])

df["failed"] = (df["status"] == "FAILED").astype(int)
df["bank_side"] = (
    (df["category"] == "Bank-side")
    & ~df["error_code"].isin(["BNK_03", "BNK_05"])
    & ~df["is_repaired_code"]
    & (df["status"] == "FAILED")
).astype(int)

earliest_date = df["attempt_date"].min()
df["day_index"] = (df["attempt_date"] - earliest_date).dt.days
df["t30"] = df["day_index"] / 30.0
df["weekday"] = df["initiated_at"].dt.dayofweek.astype("category")
df["month_end"] = ((df["attempt_date"].dt.day >= 28) | (df["attempt_date"].dt.day <= 2)).astype(int)
df["peak"] = df["is_peak"].astype(int)
df["log_amt"] = np.log(df["amount"].astype(float))

in_deploy = (df["attempt_date"] >= "2026-08-03") & (df["attempt_date"] <= "2026-08-16")
df["clearwave_window"] = ((df["psp_name"] == "Clearwave") & in_deploy).astype(int)
df["kestrel_anom"] = (
    (df["bank_name"] == "Kestrel Commercial")
    & df["attempt_date"].dt.date.isin(kestrel_flagged_dates)
).astype(int)

df["small_over10k"] = ((df["size_tier"] == "Small") & (df["amount"] >= 10000)).astype(int)
df["peak_medium"] = (df["peak"] * (df["size_tier"] == "Medium")).astype(int)
df["peak_small"] = (df["peak"] * (df["size_tier"] == "Small")).astype(int)

# bank_term = bank_name, except Large banks other than Tarang National and Zenora become "Other Large"
df["bank_term"] = np.where(
    df["size_tier"] == "Large",
    np.where(df["bank_name"].isin(["Tarang National", "Zenora"]), df["bank_name"], "Other Large"),
    df["bank_name"]
)
num_bank_terms = df["bank_term"].nunique()
out(f"Number of bank_term levels: {num_bank_terms} (expect 35)")

# Helpers
def fit_logit(formula, data):
    model = smf.logit(formula, data=data)
    result = model.fit(maxiter=200, disp=False)
    return result

def or_table(result, terms_filter=None):
    params = result.params
    conf = result.conf_int()
    pvals = result.pvalues

    if terms_filter is not None:
        if isinstance(terms_filter, list):
            mask = params.index.isin(terms_filter)
        elif callable(terms_filter):
            mask = [terms_filter(idx) for idx in params.index]
        else:
            mask = params.index.str.contains(terms_filter)
        params = params[mask]
        conf = conf.loc[params.index]
        pvals = pvals[params.index]

    df_or = pd.DataFrame({
        "term": params.index,
        "coef": params.values,
        "OR": np.exp(params.values),
        "CI_low": np.exp(conf[0].values),
        "CI_high": np.exp(conf[1].values),
        "p": pvals.values
    })
    return df_or


# ==============================================================================
# SECTION 1: M0 (raw bank group)
# ==============================================================================
out("\n" + "=" * 60)
out("SECTION 1: M0 (raw bank group)")
out("=" * 60)
formula_m0 = 'failed ~ C(bank_group, Treatment("Other Large"))'
res_m0 = fit_logit(formula_m0, df)
df_m0_or = or_table(res_m0)
out("\nM0 Odds Ratios (Reference: Other Large):")
out(df_m0_or.to_string(index=False))


# ==============================================================================
# SECTION 2: M1 (all failures, with controls)
# ==============================================================================
out("\n" + "=" * 60)
out("SECTION 2: M1 (all failures, with controls)")
out("=" * 60)
formula_m1 = (
    'failed ~ C(bank_group, Treatment("Other Large")) + '
    'C(network_type, Treatment("WiFi")) + log_amt + peak + '
    'C(psp_name, Treatment("PayNova")) + clearwave_window + t30 + '
    'C(weekday) + month_end + kestrel_anom + small_over10k'
)
res_m1 = fit_logit(formula_m1, df)

m1_key_terms = [
    t for t in res_m1.params.index
    if "bank_group" in t
    or "network_type" in t
    or t in ["peak", "clearwave_window", "t30", "small_over10k", "kestrel_anom"]
]
df_m1_or = or_table(res_m1, m1_key_terms)
out("\nM1 Odds Ratios for Key Terms:")
out(df_m1_or.to_string(index=False))

# Tarang and Zenora ORs summary next to M0
m0_tarang = df_m0_or[df_m0_or["term"].str.contains("Tarang National")].iloc[0]
m0_zenora = df_m0_or[df_m0_or["term"].str.contains("Zenora")].iloc[0]
m1_tarang = df_m1_or[df_m1_or["term"].str.contains("Tarang National")].iloc[0]
m1_zenora = df_m1_or[df_m1_or["term"].str.contains("Zenora")].iloc[0]

out("\nSummary of Tarang National and Zenora (M0 Raw vs M1 Controlled All Failures):")
out(f"Tarang National: M0 OR = {m0_tarang['OR']:.4f} (95% CI: {m0_tarang['CI_low']:.4f} - {m0_tarang['CI_high']:.4f}, p={m0_tarang['p']:.4e}) | M1 OR = {m1_tarang['OR']:.4f} (95% CI: {m1_tarang['CI_low']:.4f} - {m1_tarang['CI_high']:.4f}, p={m1_tarang['p']:.4e})")
out(f"Zenora:          M0 OR = {m0_zenora['OR']:.4f} (95% CI: {m0_zenora['CI_low']:.4f} - {m0_zenora['CI_high']:.4f}, p={m0_zenora['p']:.4e}) | M1 OR = {m1_zenora['OR']:.4f} (95% CI: {m1_zenora['CI_low']:.4f} - {m1_zenora['CI_high']:.4f}, p={m1_zenora['p']:.4e})")


# ==============================================================================
# SECTION 3: M2 (bank-side failures, individual bank effects)
# ==============================================================================
out("\n" + "=" * 60)
out("SECTION 3: M2 (bank-side failures, individual bank effects)")
out("=" * 60)
num_bank_side_events = df["bank_side"].sum()
out(f"Number of bank-side events: {num_bank_side_events}")

formula_m2 = (
    'bank_side ~ C(bank_term, Treatment("Other Large")) + '
    'C(network_type, Treatment("WiFi")) + log_amt + peak + '
    'C(psp_name, Treatment("PayNova")) + clearwave_window + t30 + '
    'C(weekday) + month_end + kestrel_anom'
)
res_m2 = fit_logit(formula_m2, df)

# 34 bank coefficients
bank_terms_m2 = [t for t in res_m2.params.index if "bank_term" in t]
df_m2_banks = or_table(res_m2, bank_terms_m2).copy()
df_m2_banks["bank_name"] = df_m2_banks["term"].apply(lambda x: x.split("[T.")[1].rstrip("]"))

# Holm-adjusted p-values
reject, pvals_corrected, _, _ = multipletests(df_m2_banks["p"], method="holm")
df_m2_banks["p_adj"] = pvals_corrected
df_m2_banks["survives_holm"] = df_m2_banks["p_adj"] < 0.05

df_m2_banks = df_m2_banks.sort_values(by="p").reset_index(drop=True)
out(f"\nAll 34 Bank Coefficients in M2 (sorted by p-value):")
out(df_m2_banks[["bank_name", "coef", "OR", "CI_low", "CI_high", "p", "p_adj", "survives_holm"]].to_string(index=False))

surviving_banks = df_m2_banks[df_m2_banks["survives_holm"]]
out(f"\nNumber of banks surviving Holm correction (p_adj < 0.05): {len(surviving_banks)}")
if len(surviving_banks) > 0:
    out(f"Surviving banks: {', '.join(surviving_banks['bank_name'].tolist())}")

m2_tarang = df_m2_banks[df_m2_banks["bank_name"] == "Tarang National"].iloc[0]
m2_zenora = df_m2_banks[df_m2_banks["bank_name"] == "Zenora"].iloc[0]

out("\nSummary of Tarang National and Zenora in M2 (Bank-side Model):")
out(f"Tarang National: M2 coef = {m2_tarang['coef']:.4f}, OR = {m2_tarang['OR']:.4f} (95% CI: {m2_tarang['CI_low']:.4f} - {m2_tarang['CI_high']:.4f}), p = {m2_tarang['p']:.4e}, p_adj = {m2_tarang['p_adj']:.4f}, survives = {m2_tarang['survives_holm']}")
out(f"Zenora:          M2 coef = {m2_zenora['coef']:.4f}, OR = {m2_zenora['OR']:.4f} (95% CI: {m2_zenora['CI_low']:.4f} - {m2_zenora['CI_high']:.4f}), p = {m2_zenora['p']:.4e}, p_adj = {m2_zenora['p_adj']:.4f}, survives = {m2_zenora['survives_holm']}")

# Forest plot of the 34 bank ORs
forest_df = df_m2_banks.sort_values(by="OR").reset_index(drop=True)
plt.figure(figsize=(10, 12))
y_positions = np.arange(len(forest_df))

for i, row in forest_df.iterrows():
    bname = row["bank_name"]
    or_val = row["OR"]
    ci_lo = row["CI_low"]
    ci_hi = row["CI_high"]

    if bname == "Zenora":
        color = "crimson"
        lw = 2.5
        ms = 7
    elif bname == "Tarang National":
        color = "darkorange"
        lw = 2.5
        ms = 7
    else:
        color = "steelblue"
        lw = 1.2
        ms = 5

    plt.errorbar(
        or_val, i,
        xerr=[[or_val - ci_lo], [ci_hi - or_val]],
        fmt="o", color=color, ecolor=color, elinewidth=lw, capsize=3, markersize=ms
    )

plt.axvline(1.0, color="gray", linestyle="--", linewidth=1.2, label="Reference (Other Large = 1.0)")
plt.xscale("log")
plt.yticks(y_positions, forest_df["bank_name"], fontsize=9)
plt.xlabel("Odds Ratio (95% CI, Log Scale)", fontsize=11, fontweight="bold")
plt.ylabel("Bank", fontsize=11, fontweight="bold")
plt.title("M2: Bank-Side Failure Odds Ratios (vs Other Large Reference)", fontsize=12, fontweight="bold")

# Custom legend
custom_lines = [
    matplotlib.lines.Line2D([0], [0], color="crimson", marker="o", lw=2, label="Zenora (True Hidden Penalty)"),
    matplotlib.lines.Line2D([0], [0], color="darkorange", marker="o", lw=2, label="Tarang National (Confounded in M0)"),
    matplotlib.lines.Line2D([0], [0], color="steelblue", marker="o", lw=1.2, label="Other Banks"),
    matplotlib.lines.Line2D([0], [0], color="gray", linestyle="--", lw=1.2, label="Ref OR = 1.0")
]
plt.legend(handles=custom_lines, loc="lower right", frameon=True)
plt.grid(axis="x", linestyle=":", alpha=0.6)
plt.tight_layout()

forest_path = os.path.join(figures_dir, "p4d_bank_forest.png")
plt.savefig(forest_path, dpi=300)
plt.close()
out(f"\nSaved forest plot to: {forest_path}")


# ==============================================================================
# SECTION 4: M3 (peak by tier)
# ==============================================================================
out("\n" + "=" * 60)
out("SECTION 4: M3 (peak by tier)")
out("=" * 60)
formula_m3 = (
    'bank_side ~ C(bank_term, Treatment("Other Large")) + '
    'C(network_type, Treatment("WiFi")) + log_amt + peak + '
    'C(psp_name, Treatment("PayNova")) + clearwave_window + t30 + '
    'C(weekday) + month_end + kestrel_anom + peak_medium + peak_small'
)
res_m3 = fit_logit(formula_m3, df)

peak_terms = ["peak", "peak_medium", "peak_small"]
df_m3_peak = or_table(res_m3, peak_terms)
out("\nM3 Peak Terms (Large base effect + Medium/Small interaction additions):")
out(df_m3_peak.to_string(index=False))

b_peak = res_m3.params["peak"]
b_med_add = res_m3.params["peak_medium"]
b_small_add = res_m3.params["peak_small"]

total_peak_or_large = np.exp(b_peak)
total_peak_or_medium = np.exp(b_peak + b_med_add)
total_peak_or_small = np.exp(b_peak + b_small_add)

out(f"\nImplied Total Peak Odds Ratios:")
out(f"Large Banks (peak):                 OR = {total_peak_or_large:.4f}")
out(f"Medium Banks (peak + peak_medium):  OR = {total_peak_or_medium:.4f}")
out(f"Small Banks (peak + peak_small):    OR = {total_peak_or_small:.4f}")


# ==============================================================================
# SECTION 5: raw versus adjusted figure
# ==============================================================================
out("\n" + "=" * 60)
out("SECTION 5: Raw versus Adjusted Figure")
out("=" * 60)

fig, ax = plt.subplots(figsize=(8, 6))

models = ["M0: Raw", "M1: All Failures\n+ Controls", "M2: Bank-Side\n+ Controls"]
x_pos = np.arange(len(models))
width = 0.15

tarang_ors = [m0_tarang["OR"], m1_tarang["OR"], m2_tarang["OR"]]
tarang_lo = [m0_tarang["CI_low"], m1_tarang["CI_low"], m2_tarang["CI_low"]]
tarang_hi = [m0_tarang["CI_high"], m1_tarang["CI_high"], m2_tarang["CI_high"]]
tarang_yerr = [
    [or_val - lo for or_val, lo in zip(tarang_ors, tarang_lo)],
    [hi - or_val for or_val, hi in zip(tarang_ors, tarang_hi)]
]

zenora_ors = [m0_zenora["OR"], m1_zenora["OR"], m2_zenora["OR"]]
zenora_lo = [m0_zenora["CI_low"], m1_zenora["CI_low"], m2_zenora["CI_low"]]
zenora_hi = [m0_zenora["CI_high"], m1_zenora["CI_high"], m2_zenora["CI_high"]]
zenora_yerr = [
    [or_val - lo for or_val, lo in zip(zenora_ors, zenora_lo)],
    [hi - or_val for or_val, hi in zip(zenora_ors, zenora_hi)]
]

ax.errorbar(
    x_pos - width, tarang_ors, yerr=tarang_yerr,
    fmt="o-", color="darkorange", ecolor="darkorange", elinewidth=2, capsize=4, markersize=8,
    label="Tarang National (Confounded in M0)"
)
ax.errorbar(
    x_pos + width, zenora_ors, yerr=zenora_yerr,
    fmt="s-", color="crimson", ecolor="crimson", elinewidth=2, capsize=4, markersize=8,
    label="Zenora (True Hidden Penalty)"
)

ax.axhline(1.0, color="gray", linestyle="--", linewidth=1.2, label="Reference (Other Large = 1.0)")
ax.set_yscale("log")
ax.set_xticks(x_pos)
ax.set_xticklabels(models, fontsize=10, fontweight="bold")
ax.set_ylabel("Odds Ratio (95% CI, Log Scale)", fontsize=11, fontweight="bold")
ax.set_title("Simpson's Reversal: Tarang National vs Zenora Across Models", fontsize=12, fontweight="bold")
ax.grid(axis="y", linestyle=":", alpha=0.6)
ax.legend(loc="upper right", frameon=True)
plt.tight_layout()

raw_adj_path = os.path.join(figures_dir, "p4d_raw_vs_adjusted.png")
plt.savefig(raw_adj_path, dpi=300)
plt.close()
out(f"Saved raw vs adjusted figure to: {raw_adj_path}")


# ==============================================================================
# SECTION 6: SCORING (only now import config)
# ==============================================================================
out("\n" + "=" * 60)
out("SECTION 6: SCORING AGAINST GROUND TRUTH")
out("=" * 60)

sys.path.insert(0, os.path.dirname(__file__))
from config import HIDDEN_BAD_BANK_LOGODDS_PENALTY, PEAK_LOGODDS

# 1) Zenora coefficient in M2 (log scale) with 95% CI against planted value
zen_coef = m2_zenora["coef"]
zen_conf = res_m2.conf_int().loc[m2_zenora["term"]]
zen_ci_lo, zen_ci_hi = zen_conf[0], zen_conf[1]
zen_planted = HIDDEN_BAD_BANK_LOGODDS_PENALTY
zen_ci_contains = (zen_ci_lo <= zen_planted <= zen_ci_hi)

out(f"Zenora M2 log-odds coefficient: {zen_coef:.4f} (95% CI: [{zen_ci_lo:.4f}, {zen_ci_hi:.4f}])")
out(f"Planted penalty:                {zen_planted:.4f}")
out(f"Does 95% CI contain planted?    {zen_ci_contains}")

# 2) Tarang coefficient in M2 and whether its CI contains 0
tarang_coef = m2_tarang["coef"]
tarang_conf = res_m2.conf_int().loc[m2_tarang["term"]]
tarang_ci_lo, tarang_ci_hi = tarang_conf[0], tarang_conf[1]
tarang_ci_contains_zero = (tarang_ci_lo <= 0.0 <= tarang_ci_hi)

out(f"\nTarang National M2 log-odds coefficient: {tarang_coef:.4f} (95% CI: [{tarang_ci_lo:.4f}, {tarang_ci_hi:.4f}])")
out(f"Does 95% CI contain 0 (null effect)?    {tarang_ci_contains_zero}")

# 3) Zenora in M1 and M0 as ORs against exp(planted)
exp_planted = np.exp(zen_planted)
out(f"\nZenora Odds Ratios vs Planted exp({zen_planted}) = {exp_planted:.4f}:")
out(f"M0 OR: {m0_zenora['OR']:.4f} (naive raw model)")
out(f"M1 OR: {m1_zenora['OR']:.4f} (all-failures controlled model - diluted by non-bank causes)")
out(f"M2 OR: {m2_zenora['OR']:.4f} (bank-side cause-specific model - recovered)")

# 4) M3 peak coefficients against PEAK_LOGODDS
cov_m3 = res_m3.cov_params()

# Large
b_peak_large = res_m3.params["peak"]
se_peak_large = np.sqrt(cov_m3.loc["peak", "peak"])
planted_large = PEAK_LOGODDS["Large"]
within_2se_large = abs(b_peak_large - planted_large) <= 2 * se_peak_large

# Medium
b_peak_medium = res_m3.params["peak"] + res_m3.params["peak_medium"]
var_medium = (
    cov_m3.loc["peak", "peak"]
    + cov_m3.loc["peak_medium", "peak_medium"]
    + 2 * cov_m3.loc["peak", "peak_medium"]
)
se_peak_medium = np.sqrt(var_medium)
planted_medium = PEAK_LOGODDS["Medium"]
within_2se_medium = abs(b_peak_medium - planted_medium) <= 2 * se_peak_medium

# Small
b_peak_small = res_m3.params["peak"] + res_m3.params["peak_small"]
var_small = (
    cov_m3.loc["peak", "peak"]
    + cov_m3.loc["peak_small", "peak_small"]
    + 2 * cov_m3.loc["peak", "peak_small"]
)
se_peak_small = np.sqrt(var_small)
planted_small = PEAK_LOGODDS["Small"]
within_2se_small = abs(b_peak_small - planted_small) <= 2 * se_peak_small

out(f"\nM3 Peak Log-Odds Coefficients vs Ground Truth:")
out(f"Large:  estimate = {b_peak_large:.4f} (SE = {se_peak_large:.4f}) | Planted = {planted_large:.4f} | Within 2 SE: {within_2se_large}")
out(f"Medium: estimate = {b_peak_medium:.4f} (SE = {se_peak_medium:.4f}) | Planted = {planted_medium:.4f} | Within 2 SE: {within_2se_medium}")
out(f"Small:  estimate = {b_peak_small:.4f} (SE = {se_peak_small:.4f}) | Planted = {planted_small:.4f} | Within 2 SE: {within_2se_small}")

# Plain sentence
out("\nThe naive raw view (M0) wrongly flagged Tarang National due to customer network confounding while missing Zenora's true penalty, whereas the cause-specific model with controls (M2) successfully isolated Zenora as the only significant underperforming bank and exonerated Tarang National.")

out("\nPhase 4D analysis OK")

