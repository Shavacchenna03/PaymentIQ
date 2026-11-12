# Reproducing PaymentIQ

This document provides step-by-step instructions to reproduce the PaymentIQ data warehouse, SQL views, analytical models, and reports from a fresh clone.

---

## Prerequisites

1. **Python 3.11** (tested on Python 3.11.4).
2. **PostgreSQL 16 or newer** with an empty database created (e.g., `paymentiq`).
3. **Environment credentials file (`.env`)** in the project root containing:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=paymentiq
   DB_USER=postgres
   DB_PASSWORD=your_password
   ```

---

## Environment Setup

1. **Create and activate a virtual environment**:
   ```bash
   # Windows PowerShell
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install project dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Notes on Data and Seeds

- **Synthetic Data & Seeds**: All data is synthetic and generated programmatically. The generator scripts use deterministic seeds (`SEED = 42`), ensuring that regenerated data, dirty injection, and downstream tables are 100% byte-for-byte reproducible.
- **Git Tracking**: Raw and processed CSV files in `data/raw/` and `data/processed/` are excluded from Git to maintain a clean repository. Running the generator steps below creates them locally.

---

## Numbered Run Order

Execute the scripts sequentially in the following numbered order.

### Step 1: Generator & Pipeline Scripts (Phases 1-2)

1. `python generator/db_check.py`
2. `python generator/create_schema.py`
3. `python generator/gen_dimensions.py`
4. `python generator/gen_intents.py`
5. `python generator/gen_failures.py`
6. `python generator/gen_latency.py`
7. `python generator/gen_retries.py`
8. `python generator/gen_events_recon.py`
9. `python generator/gen_dirty.py`
10. `python generator/clean_data.py`
11. `python generator/load_db.py`

*(All generator scripts verified present in `generator/`; none missing).*

---

### Step 2: SQL Scripts & Views (Phases 2-7)

Run each SQL script using the `run_sql.py` runner:

12. `python generator/run_sql.py sql/01_schema.sql`
13. `python generator/run_sql.py sql/02_truth_tables.sql`
14. `python generator/run_sql.py sql/03_indexes.sql`
15. `python generator/run_sql.py sql/04_validation.sql`
16. `python generator/run_sql.py sql/05_dim_date.sql`
17. `python generator/run_sql.py sql/06_views.sql`
18. `python generator/run_sql.py sql/07_phase3a_checks.sql`
19. `python generator/run_sql.py sql/08_kpi_views.sql`
20. `python generator/run_sql.py sql/09_phase3b_checks.sql`
21. `python generator/run_sql.py sql/10_heatmap_anomaly.sql`
22. `python generator/run_sql.py sql/11_phase3c_checks.sql`
23. `python generator/run_sql.py sql/12_bands.sql`
24. `python generator/run_sql.py sql/13_phase3d_checks.sql`
25. `python generator/run_sql.py sql/14_rootcause_views.sql`
26. `python generator/run_sql.py sql/15_phase4a_checks.sql`
27. `python generator/run_sql.py sql/16_bank_concentration.sql`
28. `python generator/run_sql.py sql/17_phase4b_checks.sql`
29. `python generator/run_sql.py sql/18_first_attempt_views.sql`
30. `python generator/run_sql.py sql/19_phase4c_checks.sql`
31. `python generator/run_sql.py sql/20_funnel.sql`
32. `python generator/run_sql.py sql/21_phase4f1_checks.sql`
33. `python generator/run_sql.py sql/22_journeys.sql`
34. `python generator/run_sql.py sql/23_phase5_checks.sql`
35. `python generator/run_sql.py sql/24_customer_features.sql`
36. `python generator/run_sql.py sql/25_gaps_cohorts.sql`
37. `python generator/run_sql.py sql/26_phase5_3_checks.sql`
38. `python generator/run_sql.py sql/27_value.sql`
39. `python generator/run_sql.py sql/28_phase6_1_checks.sql`
40. `python generator/run_sql.py sql/29_decisions.sql`
41. `python generator/run_sql.py sql/30_phase7_1_checks.sql`

*(All 30 SQL scripts verified present in `sql/`).*

---

### Step 3: Analysis Scripts (Phases 3-8)

Run the Python analysis and scorecard scripts:

42. `python generator/analysis_3e.py`
43. `python generator/analysis_4d.py`
44. `python generator/analysis_4e.py`
45. `python generator/scorecard_4.py`
46. `python generator/analysis_5.py`
47. `python generator/analysis_5b.py`
48. `python generator/analysis_6.py`
49. `python generator/analysis_7.py`
50. `python generator/analysis_8a.py`
51. `python generator/analysis_8b.py`

*(All analysis scripts verified present in `generator/`; none missing).*
