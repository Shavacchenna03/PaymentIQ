# Interview Case Studies (PaymentIQ)

## 1. Simpson's paradox: the wrong bank
Situation: Tarang National had the highest raw failure rate among large banks; Zenora looked average.
What I did: Checked network mix (25.9 percent of Tarang's attempts on 3G or 2G vs 14.1 percent elsewhere), then fitted cause-specific logistic models on first attempts, with all attempts as the denominator.
Result: Raw odds ratio for Tarang 1.07; with controls 1.02. Zenora 1.01 raw, 1.44 on bank-side failures (CI 1.30 to 1.60; planted 1.42).
Do differently: Test a bank by hour interaction more formally.
Likely follow-up: "Why a cause-specific model?" Because a bank penalty acts only on bank-side failures and is diluted in an all-failures model (Zenora OR 1.08 there).

## 2. Detecting an incident
Situation: A two-week PSP incident barely moved the monthly rate.
What I did: Rolling z-score flagged 3 of 14 days; a change-point likelihood search over all windows with a permutation test found the window exactly.
Result: 3 to 16 Aug, 10.66 vs 8.92 percent; adjusting for it revealed a hidden 1.0 point improvement trend.
Do differently: Add a live version with a trailing window.
Likely follow-up: "Why did z-scores fail?" The rolling baseline absorbs a sustained shift.

## 3. Journeys without an ID
Situation: No journey ID in the raw data.
What I did: Window-function rules at 15, 30 and 60 minutes plus a domain rule (a new journey starts after any success); scored against hidden intents.
Result: Merged journeys 5,171 (30 min) to 346 (domain rule), 93 percent fewer. The 60-minute rule looked closest on recovery but was right for the wrong reason.
Do differently: Learn the window from the retry-gap distribution.
Likely follow-up: "How do you know it works?" I scored it against truth.

## 4. Rules versus a model
Situation: Decide which failed payments to retry.
What I did: Built a five-way rules layer (never retry uncertain status), then a time-split logistic model.
Result: Within the eligible group AUC 0.529, top-decile lift 1.18. Recommended rules only. Retry-everything would risk 144 double charges in the test period.
Do differently: Richer features and a real system-triggered test.
Likely follow-up: "Why not ship the model?" It added little beyond the error code the rules already use.

## 5. A guardrail that overruled the metric
Situation: Design a test for a failure-message redesign.
What I did: Power analysis, a pre-registered decision rule, a non-inferiority guardrail on duplicate payments, a 1,000-repeat simulation.
Result: 96 percent power for +3 points; when duplicates rose 0.8 points the ship rate was 0.1 percent despite significant recovery.
Do differently: A real duplicate measure and per-failure-type analysis.
Likely follow-up: "Is the redesign effective?" The effect is assumed; this demonstrates the method.
