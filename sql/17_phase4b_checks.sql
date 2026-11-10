-- CHECK: 01 view totals by population
-- EXPECT: 40 banks in each; all: attempts 291859, failures 30313; first: attempts 273574, failures 24772; shares add to 100
SELECT population, COUNT(*) AS banks, SUM(attempts) AS attempts, SUM(failures) AS failures,
       ROUND(SUM(volume_share_pct), 1) AS volume_share_total, ROUND(SUM(failure_share_pct), 1) AS failure_share_total
FROM v_bank_conc GROUP BY population ORDER BY population;

-- CHECK: 02 concentration by bank size tier (all eligible attempts)
-- EXPECT: Large about 70 pct of volume and 65 to 67 pct of failures; Medium about 22 and 23; Small about 8 and 11 to 12
SELECT size_tier, COUNT(*) AS banks, ROUND(SUM(volume_share_pct), 2) AS volume_share_pct,
       ROUND(SUM(failure_share_pct), 2) AS failure_share_pct,
       ROUND(100.0 * SUM(failures) / SUM(attempts), 2) AS failure_pct
FROM v_bank_conc WHERE population = 'all' GROUP BY size_tier ORDER BY size_tier;

-- CHECK: 03 Pareto of banks by failures, top 12 (all eligible attempts)
-- EXPECT: the 8 Large banks first, each about 8 pct of failures; cumulative failure share stays below cumulative volume share
SELECT ROW_NUMBER() OVER (ORDER BY failures DESC, bank_name) AS rnk, bank_name, size_tier, attempts, failures, failure_pct,
       volume_share_pct, failure_share_pct,
       ROUND(SUM(failure_share_pct) OVER (ORDER BY failures DESC, bank_name), 2) AS cum_failure_share_pct,
       ROUND(SUM(volume_share_pct) OVER (ORDER BY failures DESC, bank_name), 2) AS cum_volume_share_pct
FROM v_bank_conc WHERE population = 'all'
ORDER BY failures DESC, bank_name LIMIT 12;

-- CHECK: 04 top 20 pct of banks (8 of 40) by failures versus their volume
-- EXPECT: top 8 failure share about 65 to 67 pct against volume share about 70 pct; all 8 are Large
WITH a AS (SELECT * FROM v_bank_conc WHERE population = 'all'),
     f AS (SELECT bank_name, ROW_NUMBER() OVER (ORDER BY failures DESC, bank_name) AS rn FROM a)
SELECT ROUND(SUM(a.failure_share_pct) FILTER (WHERE f.rn <= 8), 2) AS top8_failure_share_pct,
       ROUND(SUM(a.volume_share_pct) FILTER (WHERE f.rn <= 8), 2) AS top8_volume_share_pct,
       COUNT(*) FILTER (WHERE f.rn <= 8 AND a.size_tier = 'Large') AS large_banks_in_top8
FROM a JOIN f ON f.bank_name = a.bank_name;

-- CHECK: 05 Large and Medium banks, first attempts, rate against own tier
-- EXPECT: Tarang National the highest in Large by about 0.5 to 0.8 points (z above 3); Zenora near the tier rate; Kestrel Commercial slightly high from the outage
SELECT size_tier, bank_name, attempts, failures, failure_pct, ci_low, ci_high, rate_gap_vs_tier_pp, z_vs_tier
FROM v_bank_conc WHERE population = 'first' AND size_tier IN ('Large', 'Medium')
ORDER BY size_tier, failure_pct DESC;

-- CHECK: 06 Small banks, first attempts
-- EXPECT: about 1100 to 1400 first attempts per bank; intervals about 3 to 4 points wide, so the ranking is mostly noise
SELECT bank_name, attempts, failures, failure_pct, ci_low, ci_high, ROUND(ci_high - ci_low, 2) AS ci_width_pp, rate_gap_vs_tier_pp, z_vs_tier
FROM v_bank_conc WHERE population = 'first' AND size_tier = 'Small'
ORDER BY failure_pct DESC;

-- CHECK: 07 banks flagged by within-tier z-score
-- EXPECT: only a few flagged; chance alone flags about 5 pct (2 of 40); Tarang should be among the high flags
SELECT population, size_tier, COUNT(*) AS banks,
       COUNT(*) FILTER (WHERE z_vs_tier > 2) AS flagged_high,
       COUNT(*) FILTER (WHERE z_vs_tier < -2) AS flagged_low
FROM v_bank_conc GROUP BY population, size_tier ORDER BY population, size_tier;
