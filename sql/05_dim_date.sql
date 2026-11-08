DROP TABLE IF EXISTS dim_date CASCADE;

CREATE TABLE dim_date AS
SELECT d::date AS date_key,
       EXTRACT(YEAR FROM d)::int AS year,
       EXTRACT(MONTH FROM d)::int AS month_num,
       TO_CHAR(d, 'YYYY-MM') AS year_month,
       TO_CHAR(d, 'Mon') AS month_name,
       DATE_TRUNC('week', d)::date AS week_start,
       EXTRACT(ISODOW FROM d)::int AS iso_weekday,
       TO_CHAR(d, 'Dy') AS weekday_name,
       EXTRACT(DAY FROM d)::int AS day_of_month,
       (EXTRACT(DAY FROM d) >= 28 OR EXTRACT(DAY FROM d) <= 2) AS is_month_end_window,
       (EXTRACT(ISODOW FROM d) IN (6, 7)) AS is_weekend
FROM generate_series(DATE '2026-04-01', DATE '2026-09-30', INTERVAL '1 day') AS g(d);

ALTER TABLE dim_date ADD PRIMARY KEY (date_key);
