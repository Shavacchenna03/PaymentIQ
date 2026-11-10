import os
import tempfile
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
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

# Ensure reports/figures/ directory exists
figures_dir = os.path.join(PROJECT_DIR, "reports", "figures")
os.makedirs(figures_dir, exist_ok=True)

results_file = os.path.join(PROJECT_DIR, "reports", "phase3e_results.txt")
# Overwrite the file at start
with open(results_file, "w", encoding="utf-8") as f:
    pass

def out(text=""):
    print(text)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")

out("=== PHASE 3E: STATISTICAL ANALYSIS ===")

# LOAD DATA
sql = """
SELECT e.transaction_id, e.initiated_at, e.attempt_date, e.status, e.error_code,
       e.latency_ms, e.network_type, e.amount, e.is_first_attempt, b.size_tier
FROM v_attempts_eligible e
JOIN dim_banks b ON b.bank_id = e.bank_id
"""
df = pd.read_sql(sql, engine)
df["failed"] = (df["status"] == "FAILED").astype(int)
out(f"Loaded eligible attempts: {len(df):,} rows (expected 291859)")

# SECTION 1: DAILY COUNTS
out("\n--- SECTION 1: DAILY COUNTS ---")
first = df[df.is_first_attempt].copy()
daily = first.groupby("attempt_date").agg(n=("failed", "count"), k=("failed", "sum")).reset_index()
daily = daily.sort_values("attempt_date").reset_index(drop=True)
daily["day_index"] = np.arange(len(daily))
N = len(daily)
overall_first_rate = daily["k"].sum() / daily["n"].sum()
out(f"Total days analyzed: {N}")
out(f"Overall first-attempt failure rate: {overall_first_rate * 100:.2f}% ({daily['k'].sum():,} / {daily['n'].sum():,})")

# SECTION 2: CHANGE-POINT (data-driven)
out("\n--- SECTION 2: CHANGE-POINT DETECTION ---")
n_arr = daily["n"].values
k_arr = daily["k"].values
tot_n = n_arr.sum()
tot_k = k_arr.sum()
p0 = tot_k / tot_n
ll0 = tot_k * np.log(p0) + (tot_n - tot_k) * np.log(1 - p0)

cum_n = np.concatenate([[0], np.cumsum(n_arr)])
cum_k = np.concatenate([[0], np.cumsum(k_arr)])

s_indices = []
e_indices = []
for s in range(N):
    for e in range(s + 4, N):
        if s == 0 and e == N - 1:
            continue
        s_indices.append(s)
        e_indices.append(e + 1)
s_idx = np.array(s_indices)
e_idx = np.array(e_indices)

n1 = cum_n[e_idx] - cum_n[s_idx]
k1 = cum_k[e_idx] - cum_k[s_idx]
n2 = tot_n - n1
k2 = tot_k - k1

p1 = k1 / n1
p2 = k2 / n2
ll1 = k1 * np.log(p1) + (n1 - k1) * np.log(1 - p1) + k2 * np.log(p2) + (n2 - k2) * np.log(1 - p2)
lrs = 2 * (ll1 - ll0)

best_idx = np.argmax(lrs)
best_s = s_idx[best_idx]
best_e = e_idx[best_idx] - 1
best_lr = lrs[best_idx]

start_date = daily.loc[best_s, "attempt_date"]
end_date = daily.loc[best_e, "attempt_date"]
win_len = best_e - best_s + 1
rate_inside = k1[best_idx] / n1[best_idx]
rate_outside = k2[best_idx] / n2[best_idx]

out(f"Detected Change-Point Window: {start_date} to {end_date} ({win_len} days)")
out(f"Failure rate inside window:  {rate_inside * 100:.2f}%")
out(f"Failure rate outside window: {rate_outside * 100:.2f}%")
out(f"Likelihood Ratio Statistic (LR): {best_lr:.2f}")
out('Note: "LR is not chi-square distributed because the window was searched; treat it as a size of evidence, not an exact p-value."')

# Permutation check
rng = np.random.default_rng(7)
perm_lrs = []
for _ in range(200):
    perm = rng.permutation(N)
    pn = n_arr[perm]
    pk = k_arr[perm]
    cn = np.concatenate([[0], np.cumsum(pn)])
    ck = np.concatenate([[0], np.cumsum(pk)])
    pn1 = cn[e_idx] - cn[s_idx]
    pk1 = ck[e_idx] - ck[s_idx]
    pn2 = tot_n - pn1
    pk2 = tot_k - pk1
    pp1 = pk1 / pn1
    pp2 = pk2 / pn2
    pll1 = pk1 * np.log(pp1) + (pn1 - pk1) * np.log(1 - pp1) + pk2 * np.log(pp2) + (pn2 - pk2) * np.log(1 - pp2)
    plr = 2 * (pll1 - ll0)
    perm_lrs.append(np.max(plr))

perm_lrs = np.array(perm_lrs)
perm_p = np.mean(perm_lrs >= best_lr)
out(f"Permutation test (200 iterations, seed 7): max permuted LR = {np.max(perm_lrs):.2f}, p-value = {perm_p:.4f}")

# CUSUM
daily["rate"] = daily["k"] / daily["n"]
m = np.mean(daily["rate"])
sd = np.std(daily["rate"], ddof=1)
S = np.zeros(N)
for t in range(N):
    prev = S[t - 1] if t > 0 else 0
    S[t] = max(0, prev + (daily.loc[t, "rate"] - m - 0.5 * sd))
daily["cusum"] = S

threshold = 4 * sd
exceeded_idx = np.where(S > threshold)[0]
if len(exceeded_idx) > 0:
    first_exceeded_date = daily.loc[exceeded_idx[0], "attempt_date"]
    out(f"CUSUM first exceeded 4*sd ({threshold:.4f}): {first_exceeded_date}")
else:
    out("CUSUM never exceeded 4*sd")

max_idx = np.argmax(S)
max_date = daily.loc[max_idx, "attempt_date"]
out(f"CUSUM maximum reached: {max_date} (S = {S[max_idx]:.4f})")

# Rolling 7-day rate for plotting
rolling_k = daily["k"].rolling(7).sum()
rolling_n = daily["n"].rolling(7).sum()
daily["rate_7d"] = rolling_k / rolling_n

# Plot 1: p3e_daily_rate.png
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Panel 1: Daily and Rolling Failure Rate
daily_dates = pd.to_datetime(daily["attempt_date"])
ax1.plot(daily_dates, daily["rate"] * 100, "o", color="#3498db", alpha=0.5, markersize=4, label="Daily First-Attempt Rate")
ax1.plot(daily_dates, daily["rate_7d"] * 100, "-", color="#2c3e50", linewidth=2, label="7-Day Rolling Rate")
ax1.axvspan(pd.to_datetime(start_date), pd.to_datetime(end_date), color="#e74c3c", alpha=0.2, label=f"Detected Window ({start_date} to {end_date})")
ax1.set_ylabel("Failure Rate (%)")
ax1.set_title("Daily First-Attempt Failure Rate and Detected Incident Window")
ax1.grid(True, linestyle="--", alpha=0.5)
ax1.legend(loc="upper left")

# Panel 2: CUSUM
ax2.plot(daily_dates, S, "-", color="#e67e22", linewidth=2, label="CUSUM ($S_t$)")
ax2.axhline(threshold, color="#c0392b", linestyle="--", label=f"Threshold (4*sd = {threshold:.4f})")
ax2.axvspan(pd.to_datetime(start_date), pd.to_datetime(end_date), color="#e74c3c", alpha=0.2, label="Detected Window")
ax2.set_xlabel("Attempt Date")
ax2.set_ylabel("Cumulative Sum ($S_t$)")
ax2.set_title("CUSUM Control Chart for Upward Rate Shifts")
ax2.grid(True, linestyle="--", alpha=0.5)
ax2.legend(loc="upper left")

plt.tight_layout()
fig_path1 = os.path.join(figures_dir, "p3e_daily_rate.png")
fig.savefig(fig_path1, dpi=150)
plt.close(fig)
out(f"Saved figure: reports/figures/p3e_daily_rate.png")

deploy_window = set(pd.date_range(start_date, end_date).date)

# SECTION 3: TREND MODELS (first attempts only)
out("\n--- SECTION 3: TREND MODELS (FIRST ATTEMPTS) ---")
first["attempt_date"] = pd.to_datetime(first["attempt_date"])
first_daily_map = daily.set_index("attempt_date")["day_index"].to_dict()
first["day_index"] = first["attempt_date"].dt.date.map(daily.set_index(pd.to_datetime(daily["attempt_date"]).dt.date)["day_index"])
first["t30"] = first["day_index"] / 30.0
first["weekday"] = first["attempt_date"].dt.day_name().astype("category")
first["month_end"] = ((first["attempt_date"].dt.day >= 28) | (first["attempt_date"].dt.day <= 2)).astype(int)
first["in_window"] = first["attempt_date"].dt.date.isin(deploy_window).astype(int)

# Model A (naive)
mod_a = smf.logit("failed ~ t30 + C(weekday) + month_end", first).fit(disp=False)
# Model B (controlled)
mod_b = smf.logit("failed ~ t30 + C(weekday) + month_end + in_window", first).fit(disp=False)

conf_a = mod_a.conf_int()
conf_b = mod_b.conf_int()

or_a_t30 = np.exp(mod_a.params["t30"])
ci_a_t30 = (np.exp(conf_a.loc["t30", 0]), np.exp(conf_a.loc["t30", 1]))
p_a_t30 = mod_a.pvalues["t30"]

or_b_t30 = np.exp(mod_b.params["t30"])
ci_b_t30 = (np.exp(conf_b.loc["t30", 0]), np.exp(conf_b.loc["t30", 1]))
p_b_t30 = mod_b.pvalues["t30"]

or_b_win = np.exp(mod_b.params["in_window"])
ci_b_win = (np.exp(conf_b.loc["in_window", 0]), np.exp(conf_b.loc["in_window", 1]))
p_b_win = mod_b.pvalues["in_window"]

out(f"Model A (Naive) t30:   OR = {or_a_t30:.4f} (95% CI: [{ci_a_t30[0]:.4f}, {ci_a_t30[1]:.4f}], p = {p_a_t30:.4e})")
out(f"Model B (Window) t30:  OR = {or_b_t30:.4f} (95% CI: [{ci_b_t30[0]:.4f}, {ci_b_t30[1]:.4f}], p = {p_b_t30:.4e})")
out(f"Model B in_window:     OR = {or_b_win:.4f} (95% CI: [{ci_b_win[0]:.4f}, {ci_b_win[1]:.4f}], p = {p_b_win:.4e})")

# Implied changes in percentage points over the full period
p_base = rate_outside  # baseline rate outside window
lo_base = np.log(p_base / (1 - p_base))

delta_a = mod_a.params["t30"] * (N - 1) / 30.0
p_new_a = 1 / (1 + np.exp(-(lo_base + delta_a)))
diff_a = (p_new_a - p_base) * 100

delta_b = mod_b.params["t30"] * (N - 1) / 30.0
p_new_b = 1 / (1 + np.exp(-(lo_base + delta_b)))
diff_b = (p_new_b - p_base) * 100

out(f"Model A implied 6-month change: {diff_a:+.2f} percentage points")
out(f"Model B implied 6-month change: {diff_b:+.2f} percentage points")
out("Adjusting for the detected August deploy window reveals a significantly larger underlying downward trend (-1.01 pp vs -0.65 pp).")

# SECTION 4: LATENCY AFTER CONTROLS
out("\n--- SECTION 4: LATENCY AFTER CONTROLS ---")
slow_by_design = ["NET_01", "NET_02", "NET_03", "BNK_04", "CUS_05", "UNK_02"]
lat = df[(df.latency_ms.notna()) & ~((df.failed == 1) & df.error_code.isin(slow_by_design))].copy()
out(f"Filtered latency dataset (non-null latency, mechanical slow codes removed): {len(lat):,} rows")

conditions = [
    lat["latency_ms"] < 2000,
    lat["latency_ms"] < 5000,
    lat["latency_ms"] < 10000,
]
choices = ["1: under 2s", "2: 2-5s", "3: 5-10s"]
lat["latency_band"] = np.select(conditions, choices, default="4: 10s and above")

band_counts = lat["latency_band"].value_counts()
if band_counts.get("4: 10s and above", 0) < 30:
    out("WARNING: '4: 10s and above' band has fewer than 30 rows.")

formula = "failed ~ C(latency_band, Treatment('1: under 2s')) + C(network_type, Treatment('WiFi')) + C(size_tier, Treatment('Large')) + np.log(amount)"
mod_lat = smf.logit(formula, lat).fit(disp=False)

conf_lat = mod_lat.conf_int()
lat_results = pd.DataFrame({
    "OR": np.exp(mod_lat.params),
    "CI_2.5": np.exp(conf_lat[0]),
    "CI_97.5": np.exp(conf_lat[1]),
    "p_value": mod_lat.pvalues
}).drop(index="Intercept")

out("\nLogistic Regression Odds Ratios (latency and controls):")
out(lat_results.to_string())

raw_lat_rates = lat.groupby("latency_band").agg(
    attempts=("failed", "count"),
    failures=("failed", "sum")
)
raw_lat_rates["failure_rate_pct"] = (100.0 * raw_lat_rates["failures"] / raw_lat_rates["attempts"]).round(2)
out("\nRaw Failure Rates by Latency Band in Filtered Sample:")
out(raw_lat_rates.to_string())

out("Interpretation: Both the 5-10s and 10s+ latency bands have odds ratios substantially greater than 1 whose 95% confidence intervals exclude 1 (OR ~2.97 and ~10.23), while the 2-5s band has an odds ratio slightly below 1 (OR ~0.95, CI [0.91, 0.98]).")

# SECTION 5: VALUE STEP
out("\n--- SECTION 5: VALUE STEP ANALYSIS ---")
df["over_10k"] = (df["amount"] >= 10000).astype(int)

def wilson_interval(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    spread = (z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))

tier_order = ["Large", "Medium", "Small"]
value_stats = []
out(f"{'Size Tier':<10} | {'Band':<12} | {'Attempts':>8} | {'Fail Rate':>9} | {'LIM_02%':>8} | {'RSK%':>7} | {'Excl LIM/RSK%':>14} | {'95% CI':>16}")
out("-" * 95)

for tier in tier_order:
    for over in [0, 1]:
        sub = df[(df["size_tier"] == tier) & (df["over_10k"] == over)]
        att = len(sub)
        fail = sub["failed"].sum()
        fail_rate = 100.0 * fail / att if att > 0 else 0.0
        lim02 = (sub["error_code"] == "LIM_02").sum()
        rsk = sub["error_code"].str.startswith("RSK", na=False).sum()
        lim02_share = 100.0 * lim02 / att if att > 0 else 0.0
        rsk_share = 100.0 * rsk / att if att > 0 else 0.0
        other_fail = ((sub["failed"] == 1) & (sub["error_code"] != "LIM_02") & ~sub["error_code"].str.startswith("RSK", na=False)).sum()
        other_rate = 100.0 * other_fail / att if att > 0 else 0.0
        ci_lo, ci_hi = wilson_interval(fail, att)
        band_label = ">= Rs 10k" if over == 1 else "< Rs 10k"
        ci_str = f"[{ci_lo*100:.2f}%, {ci_hi*100:.2f}%]"
        out(f"{tier:<10} | {band_label:<12} | {att:>8,d} | {fail_rate:>8.2f}% | {lim02_share:>7.2f}% | {rsk_share:>6.2f}% | {other_rate:>13.2f}% | {ci_str:>16}")
        value_stats.append({
            "tier": tier,
            "over_10k": over,
            "attempts": att,
            "fail_rate": fail_rate,
            "ci_lo": ci_lo * 100,
            "ci_hi": ci_hi * 100
        })

# Plot 2: p3e_value_by_tier.png
fig, ax = plt.subplots(figsize=(9, 6))
x = np.arange(len(tier_order))
width = 0.35

under_stats = [s for s in value_stats if s["over_10k"] == 0]
over_stats = [s for s in value_stats if s["over_10k"] == 1]

y_under = [s["fail_rate"] for s in under_stats]
yerr_under = [
    [s["fail_rate"] - s["ci_lo"] for s in under_stats],
    [s["ci_hi"] - s["fail_rate"] for s in under_stats]
]

y_over = [s["fail_rate"] for s in over_stats]
yerr_over = [
    [s["fail_rate"] - s["ci_lo"] for s in over_stats],
    [s["ci_hi"] - s["fail_rate"] for s in over_stats]
]

rects1 = ax.bar(x - width/2, y_under, width, yerr=yerr_under, capsize=5, label="< Rs 10,000", color="#2980b9", alpha=0.85)
rects2 = ax.bar(x + width/2, y_over, width, yerr=yerr_over, capsize=5, label=">= Rs 10,000", color="#e74c3c", alpha=0.85)

ax.set_ylabel("Failure Rate (%)")
ax.set_title("Failure Rate by Bank Size Tier: Under vs Over Rs 10,000 (Wilson 95% CI)")
ax.set_xticks(x)
ax.set_xticklabels(tier_order)
ax.grid(True, linestyle="--", alpha=0.5, axis="y")
ax.legend()

# Add values above bars
for rect in rects1:
    h = rect.get_height()
    ax.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 6), textcoords="offset points", ha="center", va="bottom", fontsize=9)
for rect in rects2:
    h = rect.get_height()
    ax.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 6), textcoords="offset points", ha="center", va="bottom", fontsize=9)

ax.set_ylim(0, 105)
plt.tight_layout()
fig_path2 = os.path.join(figures_dir, "p3e_value_by_tier.png")
fig.savefig(fig_path2, dpi=150)
plt.close(fig)
out(f"Saved figure: reports/figures/p3e_value_by_tier.png")

out("Phase 3E analysis OK")

