import os
import sys
import tempfile
import math

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
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

results_file = os.path.join(PROJECT_DIR, "reports", "phase7_results.txt")
with open(results_file, "w", encoding="utf-8") as f:
    pass

def out(text=""):
    print(text)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")

out("=== PHASE 7-2: SCORING MODEL AND POLICY SIMULATION ===")

# LOAD
load_sql = """
SELECT dt.*, b.bank_name, b.size_tier, f.network_type,
       att.was_debited, att.original_status
FROM decision_table dt
JOIN dim_banks b ON b.bank_id = dt.bank_id
JOIN fact_transactions f ON f.transaction_id = dt.transaction_id
JOIN truth.attempt_truth att ON att.transaction_id = dt.transaction_id
"""
with engine.connect() as conn:
    d = pd.read_sql(load_sql, conn)

out(f"Loaded decision_table rows: {len(d)} (expected 27165)")

d['y'] = d['any_success'].astype(int)
d['initiated_at'] = pd.to_datetime(d['initiated_at'])
d = d.sort_values(['customer_id', 'initiated_at']).reset_index(drop=True)

# SPLIT
train_mask = d['initiated_at'] < '2026-08-01'
test_mask = d['initiated_at'] >= '2026-08-01'
train = d[train_mask].copy()
test = d[test_mask].copy()

out(f"Train rows (< 2026-08-01): {len(train)}, recovery rate: {train['y'].mean()*100:.2f}%")
out(f"Test rows (>= 2026-08-01): {len(test)}, recovery rate: {test['y'].mean()*100:.2f}%")

# SECTION 1 (customer action split)
out("\n--- SECTION 1: CUSTOMER ACTION SPLIT ---")
ca_rows = d[d['decision'] == 'Customer action required'].copy()

def get_action_group(row):
    ec = str(row['error_code'])
    if ec in ['CUS_01', 'CUS_02']:
        return "wrong PIN"
    elif ec == 'BNK_03':
        return "insufficient funds"
    elif ec.startswith('LIM'):
        return "limit"
    else:
        return "other"

ca_rows['action_group'] = ca_rows.apply(get_action_group, axis=1)

ca_summary = []
for grp in ["insufficient funds", "limit", "wrong PIN", "other"]:
    sub = ca_rows[ca_rows['action_group'] == grp]
    j = len(sub)
    val = sub['amount'].sum() / 100000.0
    ret_pct = (sub['n_attempts'] > 1).mean() * 100.0
    rec_pct = sub['any_success'].mean() * 100.0
    ca_summary.append({
        'action_group': grp,
        'journeys': j,
        'value_lakh': round(val, 1),
        'retried_pct': round(ret_pct, 1),
        'recovered_pct': round(rec_pct, 1)
    })

df_ca = pd.DataFrame(ca_summary)
out(df_ca.to_string(index=False))

# SECTION 2 (features)
out("\n--- SECTION 2: FEATURES ---")
d['prior_failed_starts'] = d.groupby('customer_id').cumcount()
d['retried_flag'] = (d['n_attempts'] > 1).astype(int)
d['cum_retried_prior'] = d.groupby('customer_id')['retried_flag'].cumsum() - d['retried_flag']
d['prior_retry_rate'] = np.where(d['prior_failed_starts'] > 0, d['cum_retried_prior'] / d['prior_failed_starts'], np.nan)

# Update train and test slices with the calculated features
train = d[train_mask].copy()
test = d[test_mask].copy()

train_mean_prior_retry = train['prior_retry_rate'].dropna().mean()
train['prior_retry_rate'] = train['prior_retry_rate'].fillna(train_mean_prior_retry)
test['prior_retry_rate'] = test['prior_retry_rate'].fillna(train_mean_prior_retry)

# Error code frequent grouping (< 100 train rows -> 'other')
train_code_counts = train['error_code'].value_counts()
freq_codes = set(train_code_counts[train_code_counts >= 100].index)

train['error_code_clean'] = train['error_code'].apply(lambda x: x if x in freq_codes else 'other')
test['error_code_clean'] = test['error_code'].apply(lambda x: x if x in freq_codes else 'other')

train['is_pending'] = (train['status'] == 'PENDING').astype(int)
test['is_pending'] = (test['status'] == 'PENDING').astype(int)

def get_amount_band(amt):
    if amt < 500:
        return 'under 500'
    elif amt < 2000:
        return '500-1999'
    elif amt < 10000:
        return '2000-9999'
    else:
        return '10000 and above'

train['amount_band'] = train['amount'].apply(get_amount_band)
test['amount_band'] = test['amount'].apply(get_amount_band)

train['log_amount'] = np.log(train['amount'].clip(lower=1.0))
test['log_amount'] = np.log(test['amount'].clip(lower=1.0))

train['peak'] = train['initiated_at'].dt.hour.isin([20, 21]).astype(int)
test['peak'] = test['initiated_at'].dt.hour.isin([20, 21]).astype(int)

train['in_incident'] = train['in_incident'].astype(int)
test['in_incident'] = test['in_incident'].astype(int)

train['log1p_prior_failed_starts'] = np.log1p(train['prior_failed_starts'])
test['log1p_prior_failed_starts'] = np.log1p(test['prior_failed_starts'])

cat_cols = ['error_code_clean', 'size_tier', 'network_type', 'amount_band']
num_cols = ['log_amount', 'log1p_prior_failed_starts', 'prior_retry_rate']
bin_cols = ['is_pending', 'peak', 'in_incident']

out("Feature groups:")
out(f"  Categorical: {cat_cols}")
out(f"  Standardised Numeric: {num_cols}")
out(f"  Binary: {bin_cols}")
out("Note: prior_retry_rate mostly reflects whether a customer retries, not whether a retry works.")

# One-hot encoding
train_cat = pd.get_dummies(train[cat_cols], drop_first=False, dtype=float)
test_cat = pd.get_dummies(test[cat_cols], drop_first=False, dtype=float)
train_cat, test_cat = train_cat.align(test_cat, join='left', axis=1, fill_value=0.0)

# Standardization
scaler = StandardScaler()
train_num_scaled = pd.DataFrame(scaler.fit_transform(train[num_cols]), columns=num_cols, index=train.index)
test_num_scaled = pd.DataFrame(scaler.transform(test[num_cols]), columns=num_cols, index=test.index)

X_train = pd.concat([train_num_scaled, train[bin_cols].astype(float), train_cat], axis=1)
X_test = pd.concat([test_num_scaled, test[bin_cols].astype(float), test_cat], axis=1)
y_train = train['y'].values
y_test = test['y'].values

# SECTION 3 (models, evaluated on test only)
out("\n--- SECTION 3: MODELS (EVALUATED ON TEST ONLY) ---")

# Rules-only score: train recovery rate of each decision group
rules_rate = train.groupby('decision')['y'].mean().to_dict()
test['score_rules'] = test['decision'].map(rules_rate).values

# Model score: LogisticRegression
model = LogisticRegression(max_iter=2000, C=1.0, random_state=7)
model.fit(X_train, y_train)
test['score_model'] = model.predict_proba(X_test)[:, 1]

# Overall test metrics
auc_rules_all = roc_auc_score(y_test, test['score_rules'])
brier_rules_all = brier_score_loss(y_test, test['score_rules'])
auc_model_all = roc_auc_score(y_test, test['score_model'])
brier_model_all = brier_score_loss(y_test, test['score_model'])

out(f"All Test Rows - Rules-only: AUC = {auc_rules_all:.4f}, Brier = {brier_rules_all:.4f}")
out(f"All Test Rows - Model:      AUC = {auc_model_all:.4f}, Brier = {brier_model_all:.4f}")

# Within Eligible test rows
el_mask = (test['decision'] == 'Eligible for retry evaluation').values
el_y = y_test[el_mask]
el_score = test.loc[el_mask, 'score_model'].values

auc_el = roc_auc_score(el_y, el_score)
rec_overall_el = el_y.mean()

q90_el = np.percentile(el_score, 90)
q50_el = np.median(el_score)

top_dec_mask = el_score >= q90_el
top_half_mask = el_score >= q50_el

rec_top_dec_el = el_y[top_dec_mask].mean()
rec_top_half_el = el_y[top_half_mask].mean()
lift_el = rec_top_dec_el / rec_overall_el

out(f"\nWithin 'Eligible for retry evaluation' Test Rows (N = {len(el_y)}):")
out(f"  Model AUC: {auc_el:.4f}")
out(f"  Overall recovery rate: {rec_overall_el*100:.2f}%")
out(f"  Top decile recovery rate: {rec_top_dec_el*100:.2f}%")
out(f"  Top half recovery rate: {rec_top_half_el*100:.2f}%")
out(f"  Top decile lift: {lift_el:.3f} (rules-only lift is 1.0 by construction as all Eligible rows have the same score)")

# Bootstrap intervals (500 resamples, default_rng(7))
rng = np.random.default_rng(7)
boot_aucs = []
boot_lifts = []
n_el = len(el_y)

for _ in range(500):
    idx = rng.integers(0, n_el, n_el)
    b_y = el_y[idx]
    b_s = el_score[idx]
    boot_aucs.append(roc_auc_score(b_y, b_s))
    b_overall = b_y.mean()
    b_q90 = np.percentile(b_s, 90)
    b_top_dec = b_y[b_s >= b_q90].mean()
    boot_lifts.append(b_top_dec / b_overall if b_overall > 0 else 1.0)

ci_auc = (np.percentile(boot_aucs, 2.5), np.percentile(boot_aucs, 97.5))
ci_lift = (np.percentile(boot_lifts, 2.5), np.percentile(boot_lifts, 97.5))

out(f"  Bootstrap 95% CI for Model AUC: [{ci_auc[0]:.4f}, {ci_auc[1]:.4f}]")
out(f"  Bootstrap 95% CI for Top Decile Lift: [{ci_lift[0]:.3f}, {ci_lift[1]:.3f}]")

# Calibration
test['cal_bin'] = pd.qcut(test['score_model'], q=10, duplicates='drop')
cal_table = test.groupby('cal_bin', observed=False).agg(
    mean_pred=('score_model', 'mean'),
    obs_rate=('y', 'mean'),
    count=('y', 'count')
).reset_index()

out("\nCalibration Table (10 bins of predicted probability on test):")
out(cal_table[['mean_pred', 'obs_rate', 'count']].to_string(index=False))

plt.figure(figsize=(7, 6))
plt.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
plt.plot(cal_table['mean_pred'], cal_table['obs_rate'], marker='o', linewidth=2, color='#1f77b4', label='Logistic Regression')
plt.xlabel('Mean Predicted Probability')
plt.ylabel('Observed Recovery Rate')
plt.title('Calibration Plot: Logistic Model (Test Period)')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.savefig(os.path.join(figures_dir, 'p7_calibration.png'), dpi=150)
plt.close()

# 10 largest absolute coefficients
coef_df = pd.DataFrame({
    'feature': X_train.columns,
    'coef': model.coef_[0],
    'abs_coef': np.abs(model.coef_[0])
}).sort_values('abs_coef', ascending=False)

out("\n10 Largest Absolute Coefficients:")
out(coef_df[['feature', 'coef']].head(10).to_string(index=False))

# SECTION 4 (policy simulation, test period, labelled HYPOTHETICAL COUNTERFACTUAL)
out("\n--- SECTION 4: POLICY SIMULATION (TEST PERIOD) [HYPOTHETICAL COUNTERFACTUAL] ---")

# Train retried journeys for p_code calculation
train_retried = train[train['n_attempts'] > 1]
train_retried_failed = train_retried[train_retried['status'] == 'FAILED']

code_stats = train_retried_failed.groupby('error_code').agg(
    n=('any_success', 'count'),
    rec=('any_success', 'mean')
)
class_stats = train_retried_failed.groupby('retry_class').agg(
    n=('any_success', 'count'),
    rec=('any_success', 'mean')
)
pending_rate = train_retried.loc[train_retried['status'] == 'PENDING', 'any_success'].mean()

# incident_mult: recovery rate of Safe-retry FAILED starts in incident blocks divided by outside (all periods)
safe_failed = d[(d['retry_class'] == 'Safe retry') & (d['status'] == 'FAILED')]
rec_in_inc = safe_failed.loc[safe_failed['in_incident'] == True, 'any_success'].mean()
rec_out_inc = safe_failed.loc[safe_failed['in_incident'] == False, 'any_success'].mean()
incident_mult = rec_in_inc / rec_out_inc if rec_out_inc > 0 else 1.0

out(f"Safe-retry FAILED recovery: in-incident = {rec_in_inc*100:.2f}%, outside = {rec_out_inc*100:.2f}%, incident_mult = {incident_mult:.4f}")

# Compute p for test rows
def compute_p(row):
    if row['status'] == 'PENDING':
        base_p = pending_rate
    else:
        ec = row['error_code']
        rc = row['retry_class']
        if ec in code_stats.index and code_stats.loc[ec, 'n'] >= 30:
            base_p = code_stats.loc[ec, 'rec']
        elif rc in class_stats.index:
            base_p = class_stats.loc[rc, 'rec']
        else:
            base_p = train_retried['any_success'].mean()
    if row['in_incident']:
        base_p = base_p * incident_mult
    return float(np.clip(base_p, 0.0, 1.0))

test['p'] = test.apply(compute_p, axis=1)

# already_debited: was_debited or (status PENDING and original_status SUCCESS)
test['already_debited'] = test['was_debited'] | ((test['status'] == 'PENDING') & (test['original_status'] == 'SUCCESS'))

# Policies:
# (1) retry everything: S = all test rows
# (2) rules only: S = decision "Eligible for retry evaluation"
# (3) rules plus score: S = Eligible rows with model score at or above the Eligible-row test median
el_test_median = np.median(test.loc[test['decision'] == 'Eligible for retry evaluation', 'score_model'])

policies = {
    'retry everything': test,
    'rules only': test[test['decision'] == 'Eligible for retry evaluation'],
    'rules plus score': test[(test['decision'] == 'Eligible for retry evaluation') & (test['score_model'] >= el_test_median)]
}

policy_rows = []
for pol_name, S in policies.items():
    retries_sent = len(S)
    S_inc = S[S['n_attempts'] == 1]
    incremental_journeys = len(S_inc)
    extra_recovered_lakh = (S_inc['amount'] * S_inc['p']).sum() / 100000.0
    failed_retries = (1.0 - S_inc['p']).sum()
    already_debited_count = S_inc['already_debited'].sum()
    expected_double_charges = S_inc.loc[S_inc['already_debited'], 'p'].sum()
    expected_dc_value_lakh = (S_inc.loc[S_inc['already_debited'], 'amount'] * S_inc.loc[S_inc['already_debited'], 'p']).sum() / 100000.0
    
    policy_rows.append({
        'policy': pol_name,
        'retries_sent': retries_sent,
        'incremental_journeys': incremental_journeys,
        'extra_recovered_lakh': round(extra_recovered_lakh, 2),
        'expected_failed_retries': round(failed_retries, 1),
        'already_debited': int(already_debited_count),
        'expected_double_charges': round(expected_double_charges, 1),
        'expected_double_charge_value_lakh': round(expected_dc_value_lakh, 2)
    })

df_policies = pd.DataFrame(policy_rows)
out(df_policies.to_string(index=False))
out("Policy results are hypothetical counterfactuals using observed retry success rates, not achieved results")

df_policies.to_csv(os.path.join(PROJECT_DIR, "reports", "phase7_policies.csv"), index=False)

# Figure: grouped bars for policies
fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(len(df_policies))
width = 0.35

rects1 = ax.bar(x - width/2, df_policies['extra_recovered_lakh'], width, label='Expected Extra Recovered (Lakh)', color='#2ca02c')
rects2 = ax.bar(x + width/2, df_policies['expected_double_charges'], width, label='Expected Double Charges (Count)', color='#d62728')

ax.set_ylabel('Metric Value')
ax.set_title('HYPOTHETICAL Policy Simulation (Test Period: Aug-Sep 2026)')
ax.set_xticks(x)
ax.set_xticklabels(df_policies['policy'])
ax.legend()
ax.grid(axis='y', linestyle='--', alpha=0.5)

# Add values on top of bars
for r in rects1:
    h = r.get_height()
    ax.annotate(f'{h:.1f}L', xy=(r.get_x() + r.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)
for r in rects2:
    h = r.get_height()
    ax.annotate(f'{h:.1f}', xy=(r.get_x() + r.get_width() / 2, h), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig(os.path.join(figures_dir, 'p7_policies.png'), dpi=150)
plt.close()

# SECTION 5 (incident threshold variants)
out("\n--- SECTION 5: INCIDENT THRESHOLD VARIANTS ---")

def wilson_lo_py(pos, total, z=1.959963984540054):
    if total == 0:
        return 0.0
    p = pos / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = p + z2 / (2.0 * total)
    rad = math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total))
    return 100.0 * (center - z * rad) / denom

with engine.connect() as conn:
    df_ib = pd.read_sql("""
        SELECT ib.bank_id, b.bank_name, ib.d, ib.blk, ib.attempts, ib.failures
        FROM incident_blocks ib
        JOIN dim_banks b ON b.bank_id = ib.bank_id
    """, conn)
    
    df_ib['wilson_lo'] = [wilson_lo_py(f, a) for f, a in zip(df_ib['failures'], df_ib['attempts'])]
    
    df_att = pd.read_sql("""
        SELECT a.bank_id, a.attempt_date AS d, (EXTRACT(HOUR FROM a.initiated_at)::int / 3) AS blk,
               (COALESCE(tt.incident_id, '') = 'P1_OUTAGE') AS is_p1_outage
        FROM v_attempts_eligible a
        JOIN truth.transaction_truth tt ON tt.transaction_id = a.transaction_id
    """, conn)
    
    df_safe = pd.read_sql("""
        SELECT a.customer_id, f.bank_id, f.initiated_at::date AS d, (EXTRACT(HOUR FROM f.initiated_at)::int / 3) AS blk
        FROM journey_attempts a
        JOIN fact_transactions f ON f.transaction_id = a.transaction_id
        LEFT JOIN dim_failure_codes c ON c.error_code = f.error_code
        WHERE a.n30b = 1 AND f.status IN ('FAILED','PENDING') AND c.retry_class = 'Safe retry'
    """, conn)

variants = [(15, 20), (15, 25), (25, 20), (25, 25)]
variant_rows = []

for min_att, lo_pct in variants:
    flagged = df_ib[(df_ib['attempts'] >= min_att) & (df_ib['wilson_lo'] > lo_pct)].copy()
    n_flagged = len(flagged)
    n_non_kestrel = len(flagged[flagged['bank_name'] != 'Kestrel Commercial'])
    
    flagged_keys = set(zip(flagged['bank_id'], flagged['d'], flagged['blk']))
    att_keys = list(zip(df_att['bank_id'], df_att['d'], df_att['blk']))
    is_flagged_att = np.array([k in flagged_keys for k in att_keys])
    is_p1 = df_att['is_p1_outage'].values.astype(bool)
    
    tp = np.sum(is_flagged_att & is_p1)
    fp = np.sum(is_flagged_att & (~is_p1))
    fn = np.sum((~is_flagged_att) & is_p1)
    
    recall = 100.0 * tp / (tp + fn) if (tp + fn) > 0 else 0.0
    prec = 100.0 * tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    safe_keys = list(zip(df_safe['bank_id'], df_safe['d'], df_safe['blk']))
    held = sum(k in flagged_keys for k in safe_keys)
    
    label = f"({min_att}, {lo_pct})" + (" current" if (min_att, lo_pct) == (15, 20) else "")
    variant_rows.append({
        'variant': label,
        'min_attempts': min_att,
        'lower_bound_pct': lo_pct,
        'flagged_blocks': n_flagged,
        'flagged_non_kestrel': n_non_kestrel,
        'recall_pct': round(recall, 1),
        'precision_pct': round(prec, 1),
        'safe_starts_held': held
    })

df_variants = pd.DataFrame(variant_rows)
out(df_variants.to_string(index=False))

df_variants.to_csv(os.path.join(PROJECT_DIR, "reports", "phase7_incident_variants.csv"), index=False)

out("\nPhase 7-2 analysis OK")
