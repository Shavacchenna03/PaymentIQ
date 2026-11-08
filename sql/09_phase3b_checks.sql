-- CHECK: 01 daily view totals
-- EXPECT: 183 days; eligible 291859; successes 261546; failures 30313
SELECT COUNT(*) AS days, SUM(eligible_attempts) AS eligible, SUM(successes) AS successes, SUM(failures) AS failures
FROM v_daily_kpis;

-- CHECK: 02 monthly KPIs
-- EXPECT: 6 rows summing to 291859; volume rising; first-attempt failure rate highest in August and lowest in September
SELECT year_month, eligible_attempts, failure_rate_pct, first_attempt_failure_pct, avg_success_value, mom_volume_pct, mom_first_failure_pp
FROM v_monthly_kpis ORDER BY year_month;

-- CHECK: 03 volume versus successful volume, September against April (question 3)
-- EXPECT: both ratios about 1.25 to 1.35; successes growing slightly faster than eligible attempts
SELECT ROUND(MAX(eligible_attempts) FILTER (WHERE year_month = '2026-09')::numeric / MAX(eligible_attempts) FILTER (WHERE year_month = '2026-04'), 3) AS eligible_ratio,
       ROUND(MAX(successes) FILTER (WHERE year_month = '2026-09')::numeric / MAX(successes) FILTER (WHERE year_month = '2026-04'), 3) AS success_ratio,
       ROUND(MAX(success_value) FILTER (WHERE year_month = '2026-09')::numeric / MAX(success_value) FILTER (WHERE year_month = '2026-04'), 3) AS success_value_ratio
FROM v_monthly_kpis;

-- CHECK: 04 full weeks only, first-attempt failure rate with week-over-week change
-- EXPECT: 25 full weeks (7 days); weeks starting 2026-08-03 and 2026-08-10 above their neighbours; weekly changes mostly within 1 point
SELECT week_start, eligible_attempts, first_attempt_failure_pct, wow_first_failure_pp
FROM v_weekly_kpis WHERE days_in_week = 7 ORDER BY week_start;

-- CHECK: 05 average daily volume by weekday
-- EXPECT: Saturday highest, Friday second, Sunday lowest
SELECT iso_weekday, MAX(weekday_name) AS weekday, ROUND(AVG(eligible_attempts), 0) AS avg_daily_attempts,
       ROUND(AVG(first_attempt_failure_pct), 2) AS avg_first_failure_pct
FROM v_daily_kpis GROUP BY iso_weekday ORDER BY iso_weekday;

-- CHECK: 06 month-end window versus other days
-- EXPECT: month-end days about 15 pct busier per day; failure rate slightly higher
SELECT is_month_end_window, COUNT(*) AS days, ROUND(AVG(eligible_attempts), 0) AS avg_daily_attempts,
       ROUND(100.0 * SUM(failures) / SUM(eligible_attempts), 2) AS failure_rate_pct
FROM v_daily_kpis GROUP BY is_month_end_window ORDER BY is_month_end_window;

-- CHECK: 07 ten worst days by first-attempt failure rate
-- EXPECT: several of the ten fall in 3 to 16 Aug; daily noise (about 0.75 points) means not all of them
SELECT date_key, weekday_name, first_attempts, first_attempt_failure_pct, first_attempt_failure_7d_pct
FROM v_daily_kpis ORDER BY first_attempt_failure_pct DESC LIMIT 10;

-- CHECK: 08 deploy window against the rest (3 to 16 Aug)
-- EXPECT: deploy window first-attempt failure rate about 1 point above the other days
SELECT (date_key BETWEEN DATE '2026-08-03' AND DATE '2026-08-16') AS in_deploy_window, COUNT(*) AS days,
       ROUND(100.0 * SUM(first_failures) / SUM(first_attempts), 2) AS first_attempt_failure_pct
FROM v_daily_kpis GROUP BY 1 ORDER BY 1;

-- CHECK: 09 trend, first half against second half of the period
-- EXPECT: first-attempt failure rate falls about 0.5 to 1 point from the first 91 days to the last 92 days
SELECT (day_n > 91) AS second_half, ROUND(100.0 * SUM(first_failures) / SUM(first_attempts), 2) AS first_attempt_failure_pct,
       SUM(eligible_attempts) AS eligible
FROM v_daily_kpis GROUP BY 1 ORDER BY 1;

-- CHECK: 10 derived versus true first-attempt failure rate (answer key scoring)
-- EXPECT: true rate about 8.9 to 9.1 pct; derived 9.05 pct from 3A; gap within 0.2 points
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE f.status = 'FAILED') / COUNT(*), 2) AS true_first_failure_pct,
       COUNT(*) AS true_first_eligible
FROM v_attempts_eligible f
JOIN truth.attempt_truth a ON a.transaction_id = f.transaction_id
WHERE a.attempt_number = 1;

