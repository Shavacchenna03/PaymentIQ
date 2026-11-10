# PaymentIQ: Phase Questions and Answers

A living document. Each phase adds a section when it completes. Answers are kept simple on purpose.

---

## Phase 0: Setup

Q: Why PostgreSQL and not just CSV files or Excel?
A: Real companies keep data in linked tables inside a database. Using PostgreSQL lets me show joins, window functions and schema design, which is what SQL interviews test. A single CSV cannot show that.
Interview angle: "I modelled the data relationally because payments data is naturally multi-table."

Q: Why a virtual environment (venv)?
A: It keeps this project's Python packages separate from everything else on the computer, so versions never clash and the project can be reproduced by anyone from requirements.txt.

Q: What is the .env file and why is it in .gitignore?
A: It stores the database password. If it were pushed to GitHub, anyone could read it. .gitignore tells Git never to track it.

Q: Why are the data CSVs in .gitignore?
A: Large generated files bloat the repository. The generator script is committed instead, so the data can be recreated exactly.

Q: Why use Git and GitHub from day one?
A: Every phase becomes a commit, which gives a visible history of progress. Recruiters read the commit history and README, not just the final dashboard.

Q: Why is the data synthetic?
A: Real UPI transaction data with lifecycle, retries and reconciliation is not public. Synthetic data lets me control and document the patterns. The risk is finding only what I planted, which is handled by the ground-truth check in Phase 2.

---

## Phase 1A: Lifecycle and failure taxonomy

Q: How does a UPI payment work in simple terms?
A: The customer app sends the request to PayFlow, then to its PSP, then to NPCI (the central UPI switch). NPCI asks the customer's bank to debit and the receiver's bank to credit. The result travels back to the app.

Q: Why does the number of hops matter?
A: A failure can happen at any hop. Knowing the hop is what makes root-cause analysis possible: bank, PSP, network or customer.

Q: What is the difference between an attempt and a journey?
A: An attempt is one try at paying. A journey is one intended payment, which may take several attempts. Recovery and abandonment only make sense on journeys, because a customer who fails and then succeeds has not been lost.

Q: Why is a journey defined as attempts within 30 minutes?
A: It is an assumption. If the window is too short, one retry looks like a new payment. If too long, two separate payments get merged. Phase 5 tests 15, 30 and 60 minutes and shows how much the recovery rate changes.
Interview angle: "I treated the window as a sensitivity parameter, not a fact."

Q: Why are PENDING attempts excluded from the success rate?
A: A pending payment has not finished. Counting it as failed understates reliability and counting it as success overstates it. It is excluded and reported separately as Pending Share so it stays visible.

Q: Why is a timeout not the same as a failure?
A: On a timeout the app gets no answer, but the bank may already have debited the money. That is why status must be checked before any retry.

Q: Why are the error codes not official NPCI codes?
A: Official code sets are large and partly proprietary. PayFlow uses its own illustrative codes that behave like real UPI errors. This is stated in the docs so nothing is misrepresented.

Q: What are the retry classes and why do they exist?
A: Safe retry, Customer action, Verify status first, Do not retry, Escalate. They stop the system from retrying everything blindly. Codes marked Verify status first (timeouts, duplicate request id) risk a double debit if retried.
Interview angle: this is the foundation of the Phase 7 rules layer.

Q: Can every failure be assigned to exactly one party?
A: No. The category is a best-effort label. A timeout could be network, PSP or bank. The taxonomy is illustrative, and the docs say so.

---

## Phase 1B: Metric dictionary (FINAL)

Q: Why define metrics before writing any code?
A: If SQL, Python and Power BI each calculate success rate differently, the numbers disagree and trust is lost. One dictionary with an exact numerator, denominator and window prevents that.

Q: Why is the reporting window the calendar day in IST?
A: The business operates in India, so daily and hourly patterns should line up with local time. Storing timestamps in one timezone avoids midnight errors.

Q: Why a 24-hour settlement lag before an attempt is counted?
A: Some payments resolve late. Waiting 24 hours lets most pending attempts reach a final state, so the success rate is not distorted by very recent transactions.

Q: Why is customer-cancelled (CUS_03) excluded from the failure rate?
A: A customer choosing to stop is not a reliability failure. Counting it would blame the platform for a user decision.

Q: Why keep wrong PIN and insufficient funds in the headline failure rate?
A: They are real failed payments from the business point of view. The Technical Failure Rate is shown next to it so management can see both the total and the platform-controllable part.

Q: Why report P95 latency and not only the average?
A: The average hides slow outliers. P95 shows what the slowest 1 in 20 payments experience, which is closer to the real customer pain. P50 and P99 are shown as well.

Q: What is failure concentration?
A: The share of all failures that comes from a small group, for example the top 20 percent of banks. If a few banks cause most failures, fixing those gives the biggest return. This is the Pareto idea.

Q: Why is Incremental Recovery Value labelled hypothetical?
A: It is a modelled estimate of what extra value could be recovered under assumed improvements, not an achieved result. Labelling it prevents overclaiming.

Q: Is Retry Success Rate the same as Journey Recovery Rate?
A: No. Retry Success Rate is per retry attempt. Journey Recovery Rate is per failed journey. A journey with three failed retries and one success counts as one recovered journey but four attempts.

Q: Why do Journey Recovery Rate and Abandonment Rate use the same eligible journeys?
A: So they add up to 100%. If they used different populations, the two numbers would not be complements and anyone checking would find the mismatch.

Q: Which failures are excluded from recovery metrics and why?
A: Journeys that start with a "Do not retry" code (CUS_03 customer cancelled, TEC_01 invalid request, RSK_01 risk block). Retrying these would be wrong or unsafe, so counting them as missed recoveries would be unfair.

Q: Why keep a separate Recovery Rate with no exclusion?
A: It is the pessimistic view. Placing it beside the headline rate shows management how much the exclusion changes the result, so nothing is hidden.
Interview angle: "I report the headline metric and the pessimistic version so the choice of denominator is visible."

---

## Phase 2 design: Data engineering plan

Q: Why fictional bank and PSP names?
A: Naming a real bank as unreliable would be a false claim about a real institution. Fictional names avoid that and keep the project clearly synthetic.

Q: Why no journey_id in the raw data?
A: Real companies do not have one. Deriving journeys from customer, payee, amount and time makes the 30-minute assumption testable, because the hidden truth schema holds the real intents to compare against.

Q: Why plant patterns and write them down before the analysis?
A: Planted patterns give an answer key to check the analysis against. Committing the list first shows the patterns were declared in advance, so nobody can claim they were reverse-engineered from the results.

Q: How do I answer "you just found what you planted"?
A: The patterns are known, so the test is different: do the methods recover the correct magnitudes, and do they avoid the traps. Examples are Simpson's trap (P4), the latency trap (P8) and the null effect (P9).

Q: What is the point of the null effect (P9)?
A: Device type has no true effect on failures. If the analysis reports a device effect, it is a false finding. This tests that the analysis does not invent patterns.

Q: What is Simpson's trap (P4)?
A: A pattern that reverses when you control for another variable. Bank A looks bad overall only because it handles harder transactions. Bank B looks average but is truly bad because it handles easy ones. Regression with controls separates them.

Q: Why is the retry target about 20k and not the charter's 50k?
A: With about 10 percent failures of 300k attempts, there are about 30k failures. With a 40-50 percent retry rate, that gives about 15-25k retries. 50k would need an unrealistic 20 percent failure rate.

Q: Why seed 42?
A: A fixed seed makes the random generator repeatable, so anyone can recreate the identical dataset from the committed script.

Q: Why is the truth schema hidden?
A: It holds the real answers: true intents, true segments and which timeouts really debited. Keeping it separate and unused until the end keeps the analysis honest.

---

## Phase 2A: Database schema

Q: What is a primary key and a foreign key?
A: A primary key uniquely identifies each row (transaction_id). A foreign key points to a row in another table (bank_id in transactions points to dim_banks). The database then rejects transactions that reference a bank that does not exist.

Q: Why a staging schema?
A: Raw data often arrives dirty. Staging accepts it as is, then a cleaning step loads the strict tables. This keeps the raw record and shows the cleaning work.
Interview angle: "I separated raw landing from cleaned tables, as a real pipeline does."

Q: Why CHECK constraints on the transactions table?
A: They make bad data impossible to load. A FAILED row without an error code is rejected, so the data cleaning is enforced by the database and not by memory.

Q: Why are indexes not created yet?
A: Building an index while inserting 300k rows is slower than building it once afterwards. Indexes come in step 2F.

Q: Why TIMESTAMP and not TIMESTAMPTZ?
A: Everything is stored in IST by rule (see the metric dictionary), so there is one timezone to reason about. The UTC-writing PSP is corrected during cleaning.

Q: Why does the truth schema have no link to the analysis tables?
A: It is the answer key. It only holds ids so it can be joined at the very end to compare findings against what was planted.

---

## Phase 2B: Dimension tables

Q: Why does bank size decide the volume share?
A: Real payment volume is concentrated in a few large banks. Giving the 8 Large banks about 70 percent of volume makes the top 20 percent of banks produce about 60 percent of failures, which is the failure concentration pattern (P3). Part of that is simply volume, and part is real unreliability, so the analysis has to separate them.

Q: Why is the trap bank (Tarang National) a Large bank?
A: The comparison of raw versus adjusted failure rate needs enough transactions to be statistically clear. A Large bank has them. Its raw rate looks bad only because its customers use weaker networks, and regression with controls should clear it.

Q: Why does Zenora have a penalty of +0.35 and what does it mean?
A: Log-odds is the scale logistic regression works on. +0.35 multiplies the odds of failure by about 1.42, so an 8 percent failure rate becomes about 11 percent. It is real but not huge, so the analysis must be careful to detect it among the noise.

Q: Why do Small banks get worse at peak hours?
A: Smaller banks have less infrastructure capacity, so evening load hurts them more. In the data this is a bank-by-hour interaction (P2), meaning the hour effect is not the same for every bank.

Q: Why are customer attributes assigned with exact counts instead of random sampling?
A: Exact counts give exactly 45 percent Reliable, 35 percent Tier 1 and so on. Random sampling would drift by small amounts, and exactness makes the data easier to validate.

Q: Why is the customer segment not in dim_customers?
A: Real companies do not label customers as Retry-dependent or Failure-prone. Phase 5 tries to discover the segments from behaviour alone, then compares against truth.customer_truth.

Q: Why does the script truncate tables before loading?
A: So it can be re-run safely and always gives the same result. The fact tables are empty at this stage, so nothing is lost.

Q: Why do 40 percent of customers sign up during the analysis period?
A: New customers keep joining, which creates the volume growth in P13 and gives cohorts to analyse in Phase 5.

---

## Phase 2C-1: Intent generation

Q: What is an intent?
A: A payment the customer wants to make. It becomes one or more attempts, depending on whether it fails and the customer retries. Generating intents first lets retries and journeys be built from a known truth.

Q: Why is volume built from day, weekday and hour weights?
A: Real payment traffic has rhythm: growth over time, busier weekends and month-ends, and evening peaks. The analysis in Phase 3 has to separate genuine trends from this seasonality.

Q: Why must customers transact only after their signup date?
A: Otherwise the data would contain impossible rows, and the cohort analysis in Phase 5 would be wrong. The script asserts this.

Q: What does it mean to rescale the bank tilts?
A: Tarang and Zenora attract different kinds of customers, but their total share of volume should stay as designed. Rescaling changes who uses them, not how big they are. That is what makes Simpson's trap (P4) a clean test.

Q: Why does Zenora get lower amounts?
A: Zenora's customers are mostly Tier 1 on fast networks making small payments. That makes the raw failure rate look average, while the bank truly has a penalty. Only a model with controls reveals it.

Q: Why give customers a primary and a secondary bank?
A: Real customers hold more than one account. It also means a failed payment can be retried through another bank, which matters in the recovery analysis.

Q: Why do repeat intents copy an earlier payment?
A: Two identical purchases a few minutes apart, such as two cups of tea, look like a retry but are separate intents. Phase 5 derives journeys from time and amount, so it will merge some of these wrongly, and the truth column lets us measure that error.

Q: Why use a separate random stream (SEED plus 1)?
A: So regenerating intents does not disturb the dimension tables, and each stage stays reproducible on its own.

---

## Phase 2C-2: Failure model

Q: What are competing risks?
A: Each payment faces several independent chances to fail: bank, network, PSP, customer and so on. It fails if any one fires. This lets each cause respond to its own drivers, so network quality affects network failures and bank quality affects bank failures.

Q: What is calibration and why do it?
A: The script solves for one constant per family so the average failure probability hits a target. It keeps the overall failure rate near 10 percent while the effects (peak hours, banks, networks) keep their relative size.

Q: What is log-odds, and why add effects on that scale?
A: Log-odds is the scale logistic regression uses. Effects add up there and the probability always stays between 0 and 1. A +0.35 effect multiplies the odds of failure by about 1.42.

Q: Why was the outage moved from Ridgeway to Kestrel Commercial?
A: Ridgeway handles about 1 payment per hour, so three short windows held about 15 payments, too few to detect. Kestrel is a Large bank with about 90 payments in its windows, so an anomaly check can actually see it.

Q: Why is the top-20-percent concentration about 68 percent and not 62?
A: The 8 Large banks hold 70 percent of volume, and most failures follow volume. Concentration alone does not mean unreliable banks. The real question is which banks produce more failures than their volume predicts.
Interview angle: "I separated concentration from unreliability by comparing failure share with volume share."

Q: Why was the network failure share increased?
A: For Simpson's trap to work, the confounder has to be strong enough to show in raw data. A bank with many weak-network customers must look worse than a bank with a real penalty. A small network share would have hidden the trap.

Q: Why does BNK_03 sit in the customer family when its category is Bank-side?
A: Insufficient funds is caused by the customer's balance, but the issuer reports it, so it is labelled Bank-side. The metric dictionary excludes it from the Technical Failure Rate for that reason.

Q: Why store true probabilities in failure_truth.csv?
A: They are the answer key. Later we can check whether regression recovers the real effect sizes and whether a bank's estimated penalty matches what was planted.

---

## Phase 2C-3a: Latency, pending and the debited flag

Q: Why do timeouts have a latency of about 30 seconds?
A: A timeout means the system waited until its time limit and gave up, so its latency is long by definition. That makes high latency predict failure mechanically, not causally.
Interview angle: "Slow payments fail more, but slowness is partly the symptom, not the cause. I checked by looking at non-timeout failures separately."

Q: Why is P95 latency misleading here?
A: About 4 percent of attempts are timeouts with very long latency, which is close to the 5 percent that P95 cuts off. So P95 sits right at the edge of the timeout group and moves a lot if the timeout share changes slightly. P50 and P99 should be read with it.

Q: Why does latency depend on network and bank size?
A: Weak networks and smaller banks are slower. Network quality also drives failures, so latency and failure are linked through a shared cause. This is why a raw latency-versus-failure chart can mislead.

Q: Why does the Clearwave latency ramp instead of jumping?
A: A bad deploy usually degrades gradually, then gets fixed. The ramp from 1.0x to 2.0x over 3 to 16 Aug, then a sudden drop on 17 Aug, gives a change-point that Phase 3 should detect.

Q: What does PENDING mean and why is it mostly timeouts?
A: PENDING means the payment has no final status after 24 hours. It mostly comes from uncertain-status codes because a timeout does not tell you whether the bank debited the money. That is why PENDING is excluded from the success rate and reported as Pending Share.

Q: Why do PENDING rows have no latency or completion time?
A: They never finished, so there is nothing to measure. Counting them as zero or as a failure would distort the latency percentiles and the success rate.

Q: Why did the failure rate fall slightly after PENDING was added?
A: Some failures became PENDING and left the denominator. The failure rate is failures divided by SUCCESS plus FAILED, so removing uncertain attempts changes it. This is a reporting choice, not a data change, which is why Pending Share is shown separately.

Q: Why is the debited flag only in the truth file?
A: A real company cannot see which timeouts debited the customer. Reconciliation with the bank reveals it later. Keeping the flag hidden lets Phase 7 test whether the analysis detects the risk without being told.

Q: Why is the duplicate-debit rate 3 percent and not a realistic 1 percent?
A: At 1 percent there would be only about 30 double charges, too few to measure a duplicate-payment rate. 3 percent gives enough events to analyse. The inflation is documented, so it is not mistaken for a real-world rate.

---

## Phase 2C-3b: Retry chains

Q: Why do retries depend on the error code?
A: Different failures call for different customer behaviour. A wrong PIN is easy to fix, so people retry and usually succeed. Insufficient funds usually needs a top-up first, so few retry and few succeed. Giving each group its own rates is what lets Phase 7 build retry rules from the data.

Q: Why does a PENDING first attempt get retried?
A: The customer sees no answer. Some assume it failed and pay again. If the first payment actually went through, the customer is charged twice. This is the realistic duplicate-payment scenario, and it is why status must be checked before any retry.

Q: How are double charges created?
A: A retry succeeds after an earlier attempt in the same intent that really debited the customer. The earlier debit can be a timeout flagged as debited, or a PENDING attempt that was originally a success. The flag lives only in the truth files.

Q: Why do retries during the Kestrel outage rarely succeed?
A: A retry seconds after an outage failure usually hits the same outage. In the data, retry success in the outage windows is 0.15 times the normal rate. This is why a retry rule must not fire blindly during an incident.

Q: Why do some retries happen more than 30 minutes later?
A: Some customers come back much later. About 5 percent of retries are 31 to 180 minutes after the previous attempt. A 30-minute journey window would treat those as separate journeys, which understates recovery. Phase 5 tests 15, 30 and 60 minutes to show how much this matters.

Q: Why is the retry count about 14,000 and not 20,000?
A: The failure rate is about 9 percent of 280,000 intents, so there are about 26,000 failures. With a retry rate of about 45 percent, that gives about 12,000 to 16,000 retries. Raising the retry rates to reach 20,000 would make the customers less realistic, so the target was lowered.

Q: Why does the overall failure rate rise after retries?
A: Retries add attempts, and a share of them fail again, so the attempt-level failure rate goes up. This is why journey-level metrics (recovery, abandonment) matter. A customer who fails once and then succeeds shows up as one failed attempt, but not as a lost payment.

Q: Why is there no intent_id in attempts_all.csv?
A: A real company would not have one. Phase 5 derives journeys from customer, payee, amount and time. The real intents live in the truth files so the derived journeys can be checked against them.

---

## Phase 2D: Payment events and reconciliation

Q: What is the payment events table for?
A: It records each step of a payment (initiated, sent to the PSP, issuer response, final status) with a timestamp. It shows where in the journey an attempt stopped, and how long each step took.

Q: Why do some attempts have fewer than 4 events?
A: A payment that fails early never reaches later steps. A timeout has no issuer response because the issuer never answered. A cancelled payment never reached the PSP. A PENDING payment has no final status. The missing steps are the funnel, and show where failures happen.

Q: Why do timeouts have no ISSUER_RESPONSE even though the money may have moved?
A: The platform never received the answer, which is the whole problem with timeouts. The bank may still have debited the customer. Only reconciliation later shows what really happened.

Q: What is reconciliation?
A: Comparing what the platform recorded with what actually settled at the bank. If the app shows FAILED but the settlement shows SUCCESS and money moved, that is a mismatch the finance team must fix.

Q: Why do some FAILED attempts show SUCCESS in reconciliation?
A: Debited timeouts. The customer was debited, but the app never got the answer and showed failure. If the customer then retries and succeeds, they pay twice. Reconciliation is how that is detected.

Q: Why is PENDING excluded from the Reconciliation Rate?
A: A PENDING attempt has no final status yet. Comparing it with the settlement result would count a normal late resolution as an error. PENDING is reported separately, as in the other rates.

Q: Why do 20 percent of PENDING attempts stay PENDING in reconciliation?
A: Some payments take longer than the extract window to resolve. This is realistic, and it means some real double charges are invisible in reconciliation until later.

Q: Why does settlement have a lag with a tail?
A: Most settlements complete within a day, but a small share take 1 to 3 days. This is why the metric dictionary waits 24 hours before counting an attempt, and why late settlements must not be treated as missing.

Q: Why is the random mismatch rate small (about 0.1 to 0.5 percent)?
A: Real reconciliation errors are rare. They exist so the Reconciliation Rate shows a believable figure, and so Phase 7 has to separate real double charges from random noise.

Q: Why does settlement_time exist only for SUCCESS rows?
A: Money settles only when a payment succeeds. A FAILED payment has no settlement. Leaving settlement_time empty makes that clear.

---

## Phase 2E: Deliberate data quality issues

Q: Why make the data dirty on purpose?
A: Real data always has problems. Cleaning them, and documenting how each was found and fixed, shows analytical care. It also means the analysis is run on the cleaned data, with a log of every change.

Q: How do you detect that one PSP writes UTC timestamps?
A: Compare each PSP's hourly volume profile with the others. Payments peak at 8 to 10pm IST, but QuickRail's peak appears 5 to 6 hours earlier. Its settlement lag also looks about 5.5 hours longer. Two independent signals agreeing is strong evidence.
Interview angle: "I detected the timezone issue from the data and did not just read a config flag."

Q: Why is the missing latency recovered only approximately?
A: Timestamps are stored to the second, so the difference between completion and start is within 1 second of the true latency. Adding 500 ms makes the error about 0.5 seconds on average. That is acceptable for 0.2 percent of rows, but the limit is documented.

Q: Why map FAILED rows with no error code to UNK_01?
A: A failure without a code cannot be assigned to a cause, so it goes to the Unknown category. The rows are tagged in the log so they can be excluded from root-cause analysis.

Q: How are duplicates removed safely?
A: By transaction_id. If two rows are exact copies, keep one. If they differ, the rule must be decided and logged.

Q: Why does reconciliation stay in IST when QuickRail's own data is in UTC?
A: Reconciliation comes from the bank, not from QuickRail. Data from different systems can use different conventions, and finding the mismatch is part of the cleaning work.

Q: Why were the events shifted too?
A: Events come from the same PSP system as the attempts. If only the attempts were fixed, the event timeline would no longer match the transaction.

Q: Why keep the clean files and a hidden truth file?
A: They are the answer key for cleaning. We can measure how many issues were found and how accurate the recovered values are.

---

## Phase 2F-1: Cleaning

Q: In what order should the cleaning steps run?
A: Remove duplicates first, so nothing is counted twice. Fix the timezone next, because the latency recovery depends on correct timestamps. Then fill the error codes and recover the latency. A different order can give wrong results.

Q: How does the script find the shifted PSP without a flag?
A: It compares each PSP's hourly volume profile with the other PSPs, shifted by 0 to 23 hours. A PSP whose profile matches much better after a shift is flagged. The settlement-lag gap then fixes the half hour.
Interview angle: "I used two independent signals, volume timing and settlement lag, and they agreed."

Q: Why is the settlement-lag signal needed as well?
A: Hourly profiles shift in whole hours, and the real offset is 5.5 hours. Reconciliation timestamps come from the bank in IST, so the lag gap measures the half hour.

Q: Why does the script stop if the copies of a duplicate differ?
A: Then it is no longer a simple duplicate and a rule has to be chosen. Silently picking one would hide a decision.

Q: How accurate is the recovered latency?
A: About 97 percent of rows are within 0.5 seconds, and the worst case is about 1.3 seconds. Timestamps are stored to the second, so exact recovery is impossible. The limit is stated in the log.

Q: What is the risk of mapping missing codes to UNK_01?
A: Some of these failures may really be "Do not retry" cases or a known cause. The log shows the true mix, and the rows are listed so the root-cause analysis can exclude them.

Q: Why score the cleaning against the clean files?
A: The clean files are the answer key. Scoring shows exactly what the cleaning fixed, and what error remains.

---

## Phase 2F-2: Loading, indexes and validation

Q: Why load with COPY and not row-by-row INSERT?
A: COPY streams the whole file into the table in one operation. Inserting 1.15 million event rows one batch at a time takes many minutes, while COPY takes about a minute.

Q: Why does the load order matter?
A: Foreign keys must point to rows that already exist. Transactions must be loaded before events and reconciliation, otherwise the database rejects them.

Q: Why create indexes after the load?
A: Building an index once on a full table is faster than updating it for every inserted row. Indexes speed up later queries that filter by time, bank, PSP, customer or status.

Q: Why a composite index on customer_id and initiated_at?
A: Phase 5 groups each customer's attempts in time order to build journeys. This index serves that exact pattern without a full scan.

Q: What does ANALYZE do?
A: It refreshes the statistics the query planner uses to choose between an index and a full scan. Without it, the first queries after a bulk load can be slow.

Q: Why recompute the metrics in SQL if the generator already printed them?
A: It proves the metric dictionary produces the same numbers from the database. If SQL, Python and Power BI disagree later, this is the baseline to check against.

Q: Why keep the dirty staging table in the database?
A: It preserves the raw record. Anyone can compare staging with the cleaned table and see exactly what changed, which is how a real pipeline is audited.

Q: Why is the reconciliation rate 99.73 percent and what does it mean?
A: Out of 292,483 completed attempts, 788 had a status that disagreed with the bank settlement. Most are debited timeouts, where the app showed failure but the money moved. This is the money finance would have to chase.

Q: What are the Git tags for?
A: ground-truth-declared marks the commit where the planted patterns were published before any analysis. phase-2-complete marks the finished dataset. Together they show the patterns were declared first.
Interview angle: "The answer key was committed before I ran a single analysis query, and the tag proves it."

---

## Phase 3 design and 3A: Views and first-attempt logic

Q: Why is the first-attempt failure rate the headline metric?
A: Retries depend on how customers respond, not only on system performance. A system with a lot of retries shows a higher all-attempt failure rate without being less reliable. The first attempt is the cleanest view of the system, and the all-attempt rate is shown beside it.

Q: How is a first attempt found when there is no journey_id?
A: An attempt is a first attempt if the same customer has made no earlier attempt to the same payee for the same amount in the previous 30 minutes. This uses the LAG window function.

Q: How wrong is that rule?
A: Check 03 scores it against the answer key. The 8,400 deliberate repeat purchases are labelled as retries and the retries made more than 30 minutes after a failure are labelled as new first attempts. The size of both errors is measured, not guessed.
Interview angle: "I scored my own journey rule against ground truth the first time I used it."

Q: Why did the all-attempt P95 latency (8,659 ms) differ from the generator's 7,727 ms?
A: The generator figure was first attempts only. Retries add many more slow attempts, because 38.6 percent of retries fail and many of those are timeouts. The two numbers answer different questions, so a metric always needs a stated population.

Q: Why build views instead of repeating the filters in every query?
A: The metric dictionary rules (exclude PENDING, exclude CUS_03) live in one place. If a rule changes, every query changes with it, and SQL, Python and Power BI cannot drift apart.

Q: Why a dim_date table?
A: It gives week, weekday, month-end and weekend labels in one place. This is the star-schema date dimension that Power BI will use, and it avoids repeating date logic in every query.

---

## Phase 3B: KPI views and window functions

Q: Why a 7-day rolling rate and not a daily line?
A: Daily rates swing by about 0.75 points from noise alone, and weekdays have different volumes. A 7-day window covers each weekday once, so seasonality cancels and the trend is easier to see.

Q: Why is the rolling rate computed as a sum divided by a sum?
A: Averaging daily percentages gives quiet days the same weight as busy days. Dividing total failures by total attempts over the window weights each attempt equally, which matches the metric dictionary.

Q: Why use only full weeks in the weekly trend?
A: The first and last weeks are partial and have a different weekday mix. Comparing them with a full week would show a change that is only calendar structure.

Q: Why compare September with April for volume growth?
A: Both months have 30 days, so the comparison is fair.

Q: Why did the repeat-window share change from 75 to 62.5 percent?
A: The gap is uniform from 5 to 45 minutes, so 25 of the 40 minutes fall inside the 30-minute window. The earlier figure was a mental estimate, and the measured 5,171 of 8,400 (61.6 percent) showed it was wrong. The correction was appended, not edited, to keep the history honest.
Interview angle: "I measured my own assumption, found it was wrong, and documented the correction."

Q: Why is the trend only 0.2 points between halves?
A: The Clearwave deploy (3 to 16 Aug) adds about 1.7 points for 14 days, and it falls in the second half, which hides most of the improvement. A trend must be checked with known incidents excluded or modelled.

Q: Why score the derived first-attempt rate against the truth?
A: The rule has known errors. Scoring shows the derived rate (9.05 percent) is 0.07 points from the true one (8.98 percent), so the headline metric comes with a stated error.

---

## Phase 3C: Heatmap and anomaly detection

Q: How does the anomaly flag work?
A: Each day's first-attempt failure rate is compared with the mean and standard deviation of the previous 28 days, excluding the day itself. A z-score above 2 flags the day. The baseline excludes the current day so an anomaly cannot hide itself.

Q: Why were only 3 of the 14 deploy days flagged?
A: A rolling baseline absorbs a sustained change. After a few elevated days the mean and spread rise, so later days look normal. Daily noise is about 0.75 points against a 1.7-point shift, so a z above 2 is also a high bar. A two-week shift is better found with a weekly view, CUSUM or a change-point test.
Interview angle: "I matched the detector to the anomaly type. A control chart finds spikes, a change-point test finds sustained shifts."

Q: Why did the outage show clearly at bank level but not system-wide?
A: Kestrel carries about 9 percent of attempts, and the outage covers a few hours. At bank level the z-scores are 8 to 12. System-wide they are 1.4 to 2.4. Aggregates dilute a local failure, so slice by bank before concluding that nothing happened.

Q: Why is the hourly failure rate almost flat even though peak hours hurt some banks?
A: Only Small banks degrade at peak, and they carry 8 percent of volume. By size tier, Small banks go from 3.7 to 7.3 percent while Large banks barely move. The system-wide view hides it.

Q: Why use a one-sided test (z above 2)?
A: The business cares about failure rates rising. A rate that is unusually low is not an incident. A two-sided test would add false alarms.

Q: Why not flag the first 28 days?
A: There is no baseline yet. The view requires 28 prior days, and the check confirms no flags without one.

Q: Why do night hours look noisy?
A: Hours 1 to 5 have only 700 to 1,200 attempts each over six months. Small samples move more, so any hourly chart should show volume or hide small cells.

---

## Phase 3D: Value and latency bands

Q: Why is the failure rate flat up to Rs 10,000 and then jumps?
A: Failure is about 10.2 percent in every band up to Rs 10,000, then 18.7 and 25.6 percent above. The jump is mostly per-transaction limit failures (LIM_02), plus risk blocks about 2.2 times higher. It is a step caused by policy limits, not a smooth rise with amount.

Q: What is a Wilson interval and why use it?
A: A 95 percent confidence interval for a proportion. It behaves well for small samples and for rates near 0 or 100 percent, where the simple normal formula can give impossible values. The top value bands have only 669 attempts, so their intervals are wide.

Q: Why did removing timeouts not clear the latency trap?
A: The 10 second band fell from 92 to 61 percent, not to the base rate. The remaining slow failures are BNK_04 (12 s median) and CUS_05 (60 s median), which are slow by definition. Removing only the NET codes left other mechanical failures in.

Q: Why did the 4G-only view not help?
A: Holding the network constant cannot fix a relationship that is mechanical. It also shrank the 5 to 10 second band to 2,636 attempts and left the slow-by-design codes in.
Interview angle: "A control only helps if the confounder is what drives the association. Here the cause was the failure code, so network controls did nothing."

Q: What is the honest conclusion on latency?
A: Below 5 seconds, latency says nothing about failure (about 5.2 to 5.7 percent). Above 5 seconds, failures come from timeouts and slow-by-design codes. Speeding up the platform would not by itself reduce failures.

---

## Phase 3E: Trend, change-point, latency model and value step

Q: How did the change-point search work?
A: For every possible window of 5 or more days it compared two rates, one inside the window and one outside, using a binomial likelihood. The window with the best fit was chosen. It returned 3 to 16 Aug without being told the dates.
Interview angle: "A control chart finds spikes. A likelihood search over windows finds sustained shifts."

Q: Why use a permutation test for the change-point?
A: Searching many windows makes the best likelihood ratio look larger than chance would, so the normal chi-square p-value is wrong. Shuffling the days 200 times and repeating the search shows what the best ratio looks like with no real shift. The observed 70.9 was far above the largest shuffled value of 45.9.

Q: Why did adjusting for the deploy change the trend from minus 0.65 to minus 1.0 points?
A: The 14 deploy days sit in the second half and push the failure rate up, so they hide part of the real improvement. Adding a window term separates them. A trend model must account for known incidents.

Q: Why is the latency regression not trusted?
A: Removing failures by code but keeping every success makes slow attempts look like failures, so the model finds a large effect that is not real. It also made 2G look safer than WiFi, which cannot be right. Filtering on the outcome distorts coefficients.
Interview angle: "I caught that my own control was biased. A significant coefficient is not the same as a causal one."

Q: Why is there no causal latency effect to find?
A: Latency is generated from the failure code and network type. Slow payments fail because slow codes exist, so speeding up the platform would not by itself reduce failures.

Q: What is the real explanation for the Rs 10,000 step?
A: Small banks have a Rs 10,000 per-transaction limit, so most larger payments through them fail with LIM_02. Excluding limit and risk codes, those payments fail 7.2 percent of the time. It is a policy limit, not unreliability.

Q: Why does the Small-bank figure need caution?
A: The cell has only 503 attempts. Its 95 percent interval is 87 to 93 percent, and the estimate is far from the other tiers, but small cells need a wider reading.

---

## Phase 4 design: Root-cause plan

Q: Why use cause-specific models?
A: A failure has several possible causes, each with its own drivers. A bank penalty acts only on bank-side failures. In a model of all failures it is diluted by network and customer failures. Modelling each cause separately, on all attempts as the denominator, shows the effect clearly.

Q: Why never filter rows by the outcome?
A: In Phase 3E, removing failures with certain codes but keeping all successes made slow attempts look like failures and gave 2G a lower failure risk than WiFi. The denominator must stay all eligible attempts.

Q: Why fixed effects for banks and not random effects?
A: Each of the 40 banks gets its own odds ratio, so Tarang National and Zenora can be read and scored against the answer key. Random effects shrink estimates toward the average, which would blur the two banks being tested.

Q: Why show an all-failures model as well?
A: It shows what a simple analysis would conclude. Comparing it with the bank-side model makes the dilution visible, and that is the lesson about aggregation.

Q: Why exclude the 93 repaired UNK_01 rows from code-level work?
A: Their real cause is unknown, because the cleaning mapped a missing code to UNK_01. Treating them as true unknown failures would distort code shares.

---

## Upcoming sections (added when each phase completes)

Phase 2: Data engineering. Expected topics: schema design, primary and foreign keys, how realistic failures are generated, the ground-truth file, validation checks.
Phase 3: W1 Payment performance. Expected topics: success-rate trends, window functions, P95 in SQL, value-band analysis.
Phase 4: W2 Root cause. Expected topics: Pareto, logistic regression with controls, confounders, correlation versus causation.
Phase 5: W3 Customer journey. Expected topics: sessionisation, funnels, segmentation, cohorts, window sensitivity.
Phase 6: W4 Financial impact. Expected topics: failed versus lost value, revenue-at-risk assumptions, scenario analysis.
Phase 7: W5 Recovery intelligence. Expected topics: rules versus scoring layer, idempotency, duplicate debit, model comparison.
Phase 8: W6 Experimentation. Expected topics: hypothesis, sample size, significance, confidence intervals, guardrail metrics.
Phase 9: Portfolio. Expected topics: telling the project story, defending assumptions, limitations.

