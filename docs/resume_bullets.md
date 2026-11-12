# Resume Bullets (verified numbers only)

## Title line
PaymentIQ: Payment Reliability, Root-Cause and Recovery Analytics | SQL, Python, PostgreSQL, Statsmodels, A/B Testing

## 3-line version
- Built a synthetic UPI payments warehouse in PostgreSQL (294K attempts, 1.15M events, 40 banks) with a seeded Python generator, staging-to-clean pipeline and a scored data-quality log; declared 13 patterns before analysis and scored every method against them (12 of 14 estimates within 2 SE, misses reported).
- Resolved a Simpson's paradox with cause-specific logistic regression (statsmodels, Holm-corrected): the raw view flagged the wrong bank (OR 1.07), the controlled model cleared it (1.02) and isolated the true outlier (OR 1.44 vs 1.42 planted); a change-point search recovered a 14-day PSP incident exactly.
- Quantified 297.5 lakh of unrecovered value, built a rules-based recovery layer (0 safety violations) and duplicate-debit detector (82.6% precision, 84.6% recall), and designed a pre-registered A/B test whose guardrail blocked a bad ship in simulation.

## 2-line version
- Built a seeded synthetic UPI payments warehouse (PostgreSQL, 294K attempts, 1.15M events) with 13 patterns declared before analysis; resolved a Simpson's paradox with cause-specific logistic regression (true outlier OR 1.44 vs 1.42 planted; 12 of 14 estimates within 2 SE) and found a 14-day incident exactly via change-point search.
- Quantified 297.5 lakh unrecovered value, built a rules-based recovery layer (0 safety violations) and duplicate-debit detector (82.6% precision, 84.6% recall), and designed a pre-registered A/B test with a guardrail that blocked a bad ship (simulated).

## Rules
- Say synthetic in the first bullet. Do not claim Power BI until Phase 8B is built. Do not call the experiment real.
