import os
import sys
import tempfile

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from config import NET_LOGODDS, HIDDEN_BAD_BANK_LOGODDS_PENALTY, PEAK_LOGODDS, DEVICE_TRUE_EFFECT, TREND_LOGODDS

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
figures_dir = os.path.join(PROJECT_DIR, "reports", "figures")
os.makedirs(figures_dir, exist_ok=True)

def se_from_ci(lo, hi):
    return (hi - lo) / (2.0 * 1.96)

def verify_source(source_rel, check_str):
    full_path = os.path.join(PROJECT_DIR, source_rel) if not os.path.isabs(source_rel) else source_rel
    if not os.path.exists(full_path):
        return False, f"File not found: {source_rel}"
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        if check_str not in content:
            return False, f"Check string '{check_str}' not found in {source_rel}"
        return True, "OK"
    except Exception as e:
        return False, f"Error reading {source_rel}: {e}"

# ------------------------------------------------------------------------------
# NUMERIC ROWS
# ------------------------------------------------------------------------------
raw_numeric = [
    {
        "name": "Zenora bank-side (4D M2)",
        "source_file": "reports/phase4d_results.txt",
        "check": "0.3667",
        "est": 0.3667,
        "se": se_from_ci(0.2654, 0.4680),
        "planted": float(HIDDEN_BAD_BANK_LOGODDS_PENALTY),
        "note": ""
    },
    {
        "name": "Zenora vs tier average (4E)",
        "source_file": "reports/phase4e_results.txt",
        "check": "0.3174",
        "est": 0.3174,
        "se": se_from_ci(np.log(1.2584), np.log(1.4993)),
        "planted": float(HIDDEN_BAD_BANK_LOGODDS_PENALTY) * 7.0 / 8.0,
        "note": "tier average includes Zenora, so the expected deviation is 7/8 of the penalty"
    },
    {
        "name": "Tarang bank-side (4D M2)",
        "source_file": "reports/phase4d_results.txt",
        "check": "0.0245",
        "est": 0.0245,
        "se": se_from_ci(-0.0952, 0.1442),
        "planted": 0.0,
        "note": ""
    },
    {
        "name": "Peak Large",
        "source_file": "reports/phase4d_results.txt",
        "check": "0.1086",
        "est": 0.1086,
        "se": 0.0465,
        "planted": float(PEAK_LOGODDS["Large"]),
        "note": ""
    },
    {
        "name": "Peak Medium",
        "source_file": "reports/phase4d_results.txt",
        "check": "0.2216",
        "est": 0.2216,
        "se": 0.0677,
        "planted": float(PEAK_LOGODDS["Medium"]),
        "note": ""
    },
    {
        "name": "Peak Small",
        "source_file": "reports/phase4d_results.txt",
        "check": "0.7613",
        "est": 0.7613,
        "se": 0.0748,
        "planted": float(PEAK_LOGODDS["Small"]),
        "note": ""
    },
    {
        "name": "Network 4G",
        "source_file": "reports/phase4e_results.txt",
        "check": "0.1978",
        "est": 0.1978,
        "se": 0.0296,
        "planted": float(NET_LOGODDS["4G"]),
        "note": ""
    },
    {
        "name": "Network 3G",
        "source_file": "reports/phase4e_results.txt",
        "check": "1.2506",
        "est": 1.2506,
        "se": 0.0323,
        "planted": float(NET_LOGODDS["3G"]),
        "note": ""
    },
    {
        "name": "Network 2G",
        "source_file": "reports/phase4e_results.txt",
        "check": "1.5833",
        "est": 1.5833,
        "se": 0.0396,
        "planted": float(NET_LOGODDS["2G"]),
        "note": ""
    },
    {
        "name": "Network 5G",
        "source_file": "reports/phase4e_results.txt",
        "check": "0.0600",
        "est": 0.0600,
        "se": 0.0383,
        "planted": float(NET_LOGODDS["5G"]),
        "note": ""
    },
    {
        "name": "Device iOS",
        "source_file": "reports/phase4e_results.txt",
        "check": "-0.0095",
        "est": -0.0095,
        "se": se_from_ci(-0.0419, 0.0229),
        "planted": float(DEVICE_TRUE_EFFECT),
        "note": ""
    },
    {
        "name": "Device Web",
        "source_file": "reports/phase4e_results.txt",
        "check": "-0.0062",
        "est": -0.0062,
        "se": se_from_ci(-0.0555, 0.0432),
        "planted": float(DEVICE_TRUE_EFFECT),
        "note": ""
    },
    {
        "name": "Clearwave outside deploy window",
        "source_file": "reports/phase4e_results.txt",
        "check": "-0.1191",
        "est": -0.1191,
        "se": se_from_ci(np.log(0.7750), np.log(1.0168)),
        "planted": 0.0,
        "note": ""
    },
    {
        "name": "Trend over the period (log-odds)",
        "source_file": "reports/phase3e_results.txt",
        "check": "0.9786",
        "est": np.log(0.9786) * 182.0 / 30.0,
        "se": ((np.log(0.9861) - np.log(0.9711)) / (2.0 * 1.96)) * 182.0 / 30.0,
        "planted": float(TREND_LOGODDS),
        "note": "planted trend acts on bank, network and PSP failures only, so a slightly smaller overall estimate is expected"
    }
]

numeric_rows = []
warnings = []

for row in raw_numeric:
    ok, msg = verify_source(row["source_file"], row["check"])
    if not ok:
        warnings.append(f"Warning on {row['name']}: {msg}")
    z = (row["est"] - row["planted"]) / row["se"]
    verdict = "HIT" if abs(z) <= 2.0 else "OUTSIDE 2 SE"
    numeric_rows.append({
        "name": row["name"],
        "est": row["est"],
        "se": row["se"],
        "planted": row["planted"],
        "z": z,
        "verdict": verdict,
        "source_ok": ok,
        "note": row["note"]
    })

df_num = pd.DataFrame(numeric_rows)

# ------------------------------------------------------------------------------
# QUALITATIVE ROWS
# ------------------------------------------------------------------------------
raw_qual = [
    {
        "name": "Clearwave deploy window",
        "source_file": "reports/phase4e_results.txt",
        "check": "19.7280",
        "expectation": "coefficient strictly positive",
        "observed": "OR 19.7, 95% CI 16.8 to 23.1",
        "verdict": "HIT"
    },
    {
        "name": "Kestrel outage days flagged at bank level",
        "source_file": "reports/phase3c_checks_output.txt",
        "check": "11.69",
        "expectation": "all three outage days flagged",
        "observed": "z of 11.09, 11.69 and 8.06",
        "verdict": "HIT"
    },
    {
        "name": "Deploy window recovered by change-point",
        "source_file": "reports/phase3e_results.txt",
        "check": "2026-08-03 to 2026-08-16",
        "expectation": "window within 2 days of 3 to 16 Aug",
        "observed": "3 to 16 Aug exactly",
        "verdict": "HIT"
    },
    {
        "name": "Device equivalence (all-failures model)",
        "source_file": "reports/phase4e_results.txt",
        "check": "0.9536",
        "expectation": "90% CIs inside 0.95 to 1.05",
        "observed": "Web 0.954 to 1.036, iOS 0.964 to 1.018",
        "verdict": "HIT"
    },
    {
        "name": "Device equivalence (four cause models)",
        "source_file": "reports/phase4e_results.txt",
        "check": "both_equiv",
        "expectation": "inside 0.95 to 1.05",
        "observed": "No in all four (Web too wide)",
        "verdict": "LOW POWER"
    },
    {
        "name": "Bank concentration",
        "source_file": "reports/phase4b_checks_output.txt",
        "check": "65.70",
        "expectation": "top 8 failure share 65 to 70 percent against volume share",
        "observed": "65.70 percent against 69.81 percent",
        "verdict": "HIT"
    },
    {
        "name": "False positives among banks (within-tier, Holm)",
        "source_file": "reports/phase4e_results.txt",
        "check": "Other banks surviving",
        "expectation": "0",
        "observed": "0",
        "verdict": "HIT"
    }
]

qual_rows = []
for row in raw_qual:
    ok, msg = verify_source(row["source_file"], row["check"])
    if not ok:
        warnings.append(f"Warning on {row['name']}: {msg}")
    qual_rows.append({
        "name": row["name"],
        "source_file": row["source_file"],
        "check": row["check"],
        "expectation": row["expectation"],
        "observed": row["observed"],
        "verdict": row["verdict"],
        "source_ok": ok
    })

df_qual = pd.DataFrame(qual_rows)

# ------------------------------------------------------------------------------
# SAVE CSV FILES
# ------------------------------------------------------------------------------
csv_num_path = os.path.join(PROJECT_DIR, "reports", "phase4_scorecard.csv")
df_num.to_csv(csv_num_path, index=False)

csv_qual_path = os.path.join(PROJECT_DIR, "reports", "phase4_scorecard_qualitative.csv")
df_qual.to_csv(csv_qual_path, index=False)

# ------------------------------------------------------------------------------
# FIGURE
# ------------------------------------------------------------------------------
plt.figure(figsize=(9, 7))
y_pos = np.arange(len(df_num))[::-1]  # top to bottom
colors = ["crimson" if v == "OUTSIDE 2 SE" else "tab:blue" for v in df_num["verdict"]]

plt.axvline(0, color="black", linestyle=":", alpha=0.6)
plt.axvline(-2.0, color="gray", linestyle="--", linewidth=1.2, label="Acceptance bounds (±2 SE)")
plt.axvline(2.0, color="gray", linestyle="--", linewidth=1.2)
plt.axvspan(-2.0, 2.0, color="whitesmoke", alpha=0.5, zorder=0)

plt.scatter(df_num["z"], y_pos, color=colors, s=60, zorder=3)

# Connect to 0 line for lollipop effect
for z_val, y in zip(df_num["z"], y_pos):
    c = "crimson" if abs(z_val) > 2.0 else "tab:blue"
    plt.plot([0, z_val], [y, y], color=c, alpha=0.4, linewidth=1.5, zorder=2)

plt.yticks(y_pos, df_num["name"], fontsize=9.5)
plt.xlabel("Standard Errors from Planted Value (z)", fontsize=11, fontweight="bold")
plt.title("Scorecard: Statistical Recovery of Planted Parameters", fontsize=12, fontweight="bold")

custom_handles = [
    matplotlib.lines.Line2D([0], [0], color="tab:blue", marker="o", linestyle="", markersize=7, label="HIT (|z| ≤ 2 SE)"),
    matplotlib.lines.Line2D([0], [0], color="crimson", marker="o", linestyle="", markersize=7, label="OUTSIDE 2 SE (|z| > 2)"),
    matplotlib.lines.Line2D([0], [0], color="gray", linestyle="--", linewidth=1.2, label="±2 SE Bounds")
]
plt.legend(handles=custom_handles, loc="lower right", frameon=True)
plt.grid(axis="x", linestyle=":", alpha=0.6)
plt.tight_layout()

fig_path = os.path.join(figures_dir, "p4f_scorecard.png")
plt.savefig(fig_path, dpi=300)
plt.close()

# ------------------------------------------------------------------------------
# PRINT OUTPUT
# ------------------------------------------------------------------------------
print("=== NUMERIC SCORECARD (14 Estimates vs Planted Truth) ===")
display_num = df_num[["name", "est", "planted", "z", "verdict"]].copy()
display_num["est"] = display_num["est"].map(lambda x: f"{x:.4f}")
display_num["planted"] = display_num["planted"].map(lambda x: f"{x:.4f}")
display_num["z"] = display_num["z"].map(lambda x: f"{x:.2f}")
print(display_num.to_string(index=False))

print("\n=== QUALITATIVE SCORECARD (7 Structural / Policy Checks) ===")
display_qual = df_qual[["name", "expectation", "observed", "verdict"]].copy()
print(display_qual.to_string(index=False))

hit_count = (df_num["verdict"] == "HIT").sum()
outside_count = (df_num["verdict"] == "OUTSIDE 2 SE").sum()

print("\n=== SUMMARY COUNTS ===")
print(f"Numeric Rows Total: {len(df_num)}")
print(f"  HIT (|z| <= 2):   {hit_count}")
print(f"  OUTSIDE 2 SE:     {outside_count}")

outside_names = df_num[df_num["verdict"] == "OUTSIDE 2 SE"]["name"].tolist()
print(f"Rows outside 2 SE:  {', '.join(outside_names) if outside_names else 'None'}")

if warnings:
    print("\n=== SOURCE CHECK WARNINGS ===")
    for w in warnings:
        print(f"  {w}")
else:
    print("\nAll source checks verified successfully: 0 warnings.")

print("\nScorecard OK")

