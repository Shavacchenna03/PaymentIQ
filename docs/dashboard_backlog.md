# Dashboard Backlog (Power BI)

Decision (after Phase 3): analysis phases come first. All five pages are built together in Phase 8B so styling and the data model stay consistent. Power BI Desktop runs on Windows only.

| Page | Workstream | Data produced in | Status | Design doc |
|---|---|---|---|---|
| 1 Executive Overview | W1 | Phase 3 | SKIPPED, analysis done, build pending | docs/powerbi_page1_design.md |
| 2 Failure Intelligence | W2 | Phase 4 | Design written, build pending | docs/powerbi_page2_design.md |
| 3 Customer Behaviour | W3 | Phase 5 | Design written, build pending | docs/powerbi_page3_design.md |
| 4 Recovery and Financial Impact | W4, W5 | Phases 6 and 7 | Design written (W4 and W5), build pending | docs/powerbi_page4_design.md |
| 5 Product Experiments | W6 | Phase 8 | Design written, build pending | docs/powerbi_page5_design.md |

## Page 1 data sources already in PostgreSQL
v_daily_kpis, v_weekly_kpis, v_monthly_kpis, v_heatmap_hour_weekday, v_anomaly_system, v_anomaly_kestrel, v_value_bands, v_latency_bands, v_attempts_eligible, dim_date, dim_banks, dim_psp.

## Page 1 open items for the build
- DAX measures named as in docs/metric_dictionary.md (one per KPI).
- Cards for P95 latency (all attempts and first attempts) and pending share need a query or measure on v_attempts_flagged.
- Mark the 3 to 16 Aug deploy window on the daily chart (found by change-point in Phase 3E).
- Hide heatmap cells under 500 attempts.

## Rule for every phase
At the end of each analysis phase: write docs/powerbi_pageN_design.md, list the views and tables the page needs, and update this table.



## Page 2 planned data sources (Phase 4)
v_failures_coded, v_attempts_rc, v_repaired_codes (created in 4A), plus bank-level and PSP-level result tables saved by the Phase 4 scripts. Design doc written at 4F.