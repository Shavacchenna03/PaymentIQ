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

## Phase 4A: Failure taxonomy applied

Q: What does the code Pareto show?
A: The failure codes are spread widely. It takes 10 codes to cover 79 percent of failures. The top three are timeouts (NET_01, NET_02, NET_03), 40 percent of failures together, and all are "Verify status first".

Q: Why does that matter for recovery?
A: The largest block of failures cannot be safely retried until the true status is known. A retry rule that treats timeouts like a temporary outage would risk double debits.

Q: Why does the retry class split look the way it does?
A: Verify status first is 52 percent, Safe retry 25 percent, Customer action 19 percent, and Do not retry plus Escalate about 4 percent. Only a quarter of failures are candidates for a simple automatic retry.

Q: Why do retries have a different failure mix from first attempts?
A: Retry behaviour selects which failures come back. PSP-side failures are 16.7 percent of retry failures against 11.9 percent of first-attempt failures, because safe-retry codes are retried more often and a failed retry repeats its previous code 70 percent of the time.
Interview angle: "Retries are a selected, correlated sample, so I measure causes on first attempts."

Q: How was the technical failure rate affected by the repaired rows?
A: The 93 repaired rows sit in Unknown, but 78 were really network, bank or PSP failures. The technical rate (8.07 percent) is understated by about 0.03 points.

---

## Phase 4B: Bank concentration

Q: Why do the top 8 banks hold 65.7 percent of failures on 69.8 percent of volume?
A: They are the 8 Large banks, and most failures follow volume. Large banks under-contribute, Small banks (8.25 percent of volume, 11.28 percent of failures) over-contribute by about 1.4 times. Concentration alone does not mean unreliability.

Q: What is the excess-failures measure?
A: Observed failures minus the failures the bank's volume share would predict. Positive means more failures than its size explains.

Q: Why compare each bank with its own tier?
A: Otherwise every Large bank looks good and every Small bank looks bad just because of tier.

Q: Why is the within-tier comparison misleading here?
A: It flags Tarang National (z 2.66) and shows Zenora as average (z of minus 0.06). Tarang has many weak-network customers and Zenora has a hidden bank penalty, so the simple view points at the wrong bank. This is the Simpson's setup that 4D tests.

Q: Why not name the worst Small bank?
A: Each Small bank has about 1,100 to 1,400 first attempts, so intervals are about 4 points wide, and with 18 banks tested a few flags appear by chance. The tier rate (14.17 percent) is the usable result.

Q: Why are 4C and 4D on first attempts only?
A: Retry outcomes come from retry behaviour, not from bank, network or hour, so they dilute the effects. The derived first-attempt flag misclassifies about 1.6 percent of rows, which biases effects slightly toward zero.

---

## Phase 4C and 4D: Network confounding and the Simpson's regression

Q: Why does Tarang National look worse than the other Large banks?
A: 25.9 percent of its attempts are on 3G or 2G, against 14.1 percent for the other Large banks. Inside every network group it is within 0.4 points of them.

Q: Why does Zenora look average?
A: 54.7 percent of its attempts are on fast networks and its payments are small, which hides a real bank penalty. Inside every network group it is above the other Large banks.

Q: What did the four models show?
A: M0 (raw) flagged Tarang (OR 1.07) and cleared Zenora (OR 1.01). M1 (all failures, with controls) cleared Tarang (0.99) and showed Zenora weakly (1.08). M2 (bank-side failures with controls) cleared Tarang (OR 1.02) and exposed Zenora (OR 1.44, 95 percent CI 1.30 to 1.60). The planted value was 1.42.
Interview angle: "The raw comparison pointed at the wrong bank. Controlling for network and modelling the right cause pointed at the right one."

Q: Why is Zenora diluted in the all-failures model?
A: Its penalty acts only on bank-side failures. Network and customer failures make up most failures and carry no Zenora effect, so the signal is small relative to the noise.

Q: Why did 32 of 34 banks survive the Holm correction?
A: Medium and Small banks have higher baseline bank-side failure than the Large reference group, so almost all differ from it. That is a tier baseline, not 32 findings. Banks should be judged against their own tier.

Q: What was the Holm correction for?
A: With 34 coefficients, a few would look significant by chance. Holm adjusts the p-values so the chance of any false flag stays at 5 percent.

Q: What did the peak model show?
A: Peak hours raise bank-side failure by 2.14 times at Small banks (planted 2.2), 1.25 times at Medium (planted 1.28) and 1.11 times at Large (planted 1.0). The Large estimate is 2.3 standard errors above the planted value, probably because the Kestrel outage falls in the evening and is only partly absorbed by the anomaly-day dummy. It is reported as a limitation.

Q: Why is the Small bank at 10,000 rupees or more control so large (OR 92)?
A: Small banks have a per-transaction limit of 10,000 rupees. It is a policy limit, included as a control so that Small banks are not blamed for it.

---

## Phase 4E: Device null, network, PSP and within-tier banks

Q: Why one likelihood-ratio test for device?
A: Device has three levels, so pairwise tests multiply the chance of a false flag. One test with 2 degrees of freedom asks whether device improves the model at all. Result: p = 0.84.

Q: Does a large p-value prove device has no effect?
A: No. The equivalence check asks whether the 90 percent interval for each odds ratio lies inside 0.95 to 1.05. It does in the all-failures model (iOS 0.964 to 1.018, Web 0.954 to 1.036), so device is within plus or minus 5 percent overall. In the four cause-specific models Web fails the check because it has only 21,831 attempts, so there we can only say no effect was detected.
Interview angle: "Absence of evidence is not evidence of absence, so I tested equivalence with a stated margin, and reported where power was too low."

Q: How well were network effects recovered?
A: 3G (1.25 against 1.2), 4G (0.20 against 0.15) and 5G (0.06 against 0) are within 2 standard errors. 2G is 1.58 against 1.5, which is 2.1 standard errors, a marginal miss. With four coefficients one marginal miss is not surprising. A small upward bias from the derived first-attempt flag or from competing risks is possible but untested.

Q: Is Clearwave unreliable?
A: Only during 3 to 16 Aug (odds ratio 19.7). Outside the window its odds ratio is 0.89 (interval 0.78 to 1.02, contains 1). Ignoring the window makes it look permanently worse (odds ratio 1.98).

Q: Why compare each bank with its tier average?
A: In 4D almost every Medium and Small bank looked significant because their baseline is higher than the Large reference. Deviations from the tier average ask which banks are worse than their peers. Standard errors use the covariance matrix because the average is built from estimated coefficients.

Q: Which banks differ from their tier?
A: Only Zenora (odds ratio 1.37, Holm-adjusted p below 0.0001). Tarang National does not (0.98). No other bank survives. Udaan had p = 0.034 before correction and was removed by Holm.

Q: Why is Zenora's deviation (0.317) lower than in 4D (0.367)?
A: The tier average includes Zenora, which raises the average by about 0.05.

---

## Phase 4F-1: Event funnel

Q: What does the event funnel show?
A: Where in the payment lifecycle each attempt stopped: at the platform (never sent to the PSP), after being sent with no final status (PENDING), with a final status but no issuer response, or through the full lifecycle. It localises a failure in the pipeline.

Q: Does the funnel tell us why a payment failed?
A: No. It tells us where the process stopped. Timeouts and PSP errors have no issuer response because the issuer never answered, but a missing response does not say whether the network, the PSP or the bank was at fault.
Interview angle: "The funnel locates the failure, the model attributes the cause."

Q: Why is the stop point derived from the events and not from the error code?
A: So it is measured and not assumed. Check 03 then compares the measured stop point with the taxonomy as a consistency check.

Q: Why does a missing issuer response matter for recovery?
A: If the issuer never responded, the platform does not know whether the debit happened. These attempts are the ones where status must be checked before any retry.

Q: Why measure step timing on successes only?
A: Failures stop at different points, so their step times are not comparable. Successes all pass every step.

---

## Phase 4F-2: Scorecard against planted values

Q: What does the scorecard test?
A: Whether the methods recovered what was planted. Each estimate is compared with its planted value in standard errors. Within 2 is a hit, beyond 2 is reported as outside 2 SE.

Q: Why report the misses?
A: With 14 estimates, one or two beyond 2 standard errors is expected by chance (about 5 percent each). Large peak (2.3 SE) and 2G (2.1 SE) are both just outside. Hiding them would make the scorecard unfalsifiable.
Interview angle: "The scorecard has misses, and I can say why. That is what makes the hits credible."

Q: Why is the expected within-tier Zenora deviation 7/8 of the penalty?
A: The Large tier average includes Zenora, so it rises by one eighth of the penalty and the deviation shrinks by the same amount.

Q: Why does the scorecard use transcribed estimates?
A: Parsing text results is brittle. Each row names its source file and a check string that must appear in it, so a typo is caught.

Q: Why is the trend estimate expected to be slightly smaller than the planted value?
A: The planted trend acts on bank, network and PSP failures but not on customer, limit or risk failures, so the overall effect is diluted.

Q: What does the "low power" row mean?
A: In the four cause-specific models Web has too few attempts for its interval to fit inside plus or minus 5 percent. It says nothing about the device effect itself.

---

## Phase 4F-3: RCA report and notebook

Q: Why does the report state a hypothetical improvement?
A: Removing Zenora's penalty would cut its bank-side failure odds by about 31 percent, roughly 200 first-attempt failures, under 1 percent of all failures. It is a scenario, not a result, and financial sizing waits for Phase 6.

Q: Why is the notebook read-only?
A: It loads saved results and figures and tells the story, so it runs fast and cannot drift from the verified outputs.

Q: What is the main message of Phase 4?
A: Aggregates and raw comparisons mislead. Concentration reflects volume, the worst-looking bank is clean, and the real outlier only appears with controls and the right cause-specific outcome.

---

## Phase 5-1: Journey derivation and scoring

Q: How are journeys derived without a journey_id?
A: Attempts by the same customer to the same payee for the same amount are ordered in time. A new journey starts when the gap from the previous attempt exceeds the window (15, 30 or 60 minutes). A window function numbers the journeys.

Q: What is the w30b variant?
A: The 30-minute rule plus one more condition: a new journey also starts if the previous attempt succeeded. A retry only follows a failure, so an identical purchase after a success is a new intent. It removes most of the repeat-purchase merging.
Interview angle: "I improved the rule with domain logic and measured the improvement against hidden truth."

Q: What is a merged journey and what is a split intent?
A: A merged journey contains attempts from more than one true intent, for example two identical cups of tea. A split intent has its attempts spread across more than one derived journey, for example a retry made hours later.

Q: Why does the window length matter?
A: A short window splits late retries into new journeys, which lowers measured recovery. A long window merges separate purchases, which raises it. Check 04 shows the recovery rate under each window against the truth.

Q: Why must recovery and abandonment add to 100 percent?
A: They use the same eligible journeys, as the metric dictionary requires. Check 05 verifies it for every variant.

---

## Phase 5-2: Retry timing, funnel and segmentation

Q: How long do customers wait before retrying?
A: The median gap is under a minute, with a long tail. About 5 percent of retries come after more than 30 minutes, which is what a 30-minute window cannot see.

Q: What does the recovery funnel show?
A: Of eligible failed journeys about 45 percent are retried and about a third recover. Most unrecovered journeys were never retried, so the biggest lever is getting customers to try again, not making retries succeed.

Q: Why segment blind and score afterwards?
A: A real company has no segment labels. The rules and k-means see only behaviour. The hidden labels are read last, so the agreement is an honest measure.

Q: Why use both rules and k-means?
A: Rules are explainable and can be written into a product. K-means is a data-driven comparison. If it does not beat the rules, the simpler method wins.
Interview angle: "I started with an interpretable baseline and only kept the complex method if it earned its place."

Q: Why require at least 5 journeys per customer?
A: Customers have a median of about 7 intents and failures occur in about 10 percent of them, so rates from very few journeys are mostly noise.

Q: Why will some segments be hard to recover?
A: Reliable, Failure-prone and Retry-dependent differ only slightly in failure rate, and with a few failures per customer the estimates are noisy. The scoring section reports the recall for each.

---

## Phase 5-3: Gaps, cohorts and wrap-up

Q: Why did the first retry-gap view show 0 percent above 30 minutes?
A: It only joined attempts inside the same w30b journey, and w30b starts a new journey after 30 minutes, so late retries were excluded by construction. The corrected view has no cut and is checked against the true gaps.
Interview angle: "A metric computed on a filtered population can hide the thing you are measuring."

Q: Why cap the corrected gap at 180 minutes?
A: Without a cap, any later purchase of the same amount would count as a retry. 180 minutes is the longest planted gap. In real data the cap would be tuned.

Q: What is a cohort and why look at it?
A: Customers grouped by signup month. It shows whether newer customers behave differently. Newer cohorts are small, so intervals are wide and differences should not be over-read.

Q: Why are segments not shown on the dashboard?
A: At about 0.7 failures per customer they cannot be recovered reliably, so showing them would imply a precision the data lacks.

Q: What is the main message of Phase 5?
A: Most unrecovered failures were never retried, recovery depends on the failure code, and the journey definition matters: a domain-aware rule (w30b) beats a pure time window.

---

## Phase 6-1: Value views

Q: Is a failed payment lost revenue?
A: No. Many failed journeys are retried and succeed. The three measures are kept apart: failed value (failed first attempts), recovered value (failed-first journeys that later succeeded) and unrecovered value (eligible failed-first journeys with no success).

Q: Why is recovery by value different from recovery by count?
A: Failures are not spread evenly across amounts. Large payments through Small banks fail on the per-transaction limit and rarely recover, so recovery by value is lower than recovery by count.

Q: Why exclude do-not-retry journeys from recovery value?
A: Retrying a cancelled or blocked payment would be wrong, so counting it as a missed recovery would overstate the opportunity, as with the rates in the metric dictionary.

Q: Why is transaction value not company revenue?
A: A PSP earns a fee on the payment, not the payment amount. Revenue at risk is the unrecovered value times an assumed take rate, shown with a sensitivity range.

Q: What is the reconciliation exposure?
A: Attempts where the app and the bank disagree, for example a failed timeout that actually debited the customer. It is finance-side money to chase, separate from recovery.

Q: Why score against the hidden intents?
A: Derived journeys misgroup a few attempts, so the derived values can be off. Check 09 shows by how much.

---

## Phase 6-2: Scenario model

Q: How is a scenario gain calculated?
A: A gain of g points moves g percent of the pool's journeys from unrecovered to recovered, at the average amount of that pool's unrecovered journeys. It assumes the extra recoveries look like the average unrecovered journey.

Q: Why separate retry-addressable value from limit value?
A: Limit failures such as LIM_02 are a policy limit and do not respond to retries. Mixing them would overstate what retry logic can recover. They get their own speculative scenario, for example an alternative payment option.

Q: Why is the revenue figure so much smaller than the transaction value?
A: Revenue is the recovered value times an assumed take rate (0.5 percent base, 0.3 to 1.0 range). A PSP earns a fee, not the payment amount.
Interview angle: "I kept transaction value and revenue separate, and showed the take rate as an assumption with a range."

Q: Why bootstrap the intervals?
A: Value is heavy-tailed, since a few large limit-blocked payments dominate. A bootstrap over journeys shows how much totals move if the sample were different, without assuming a distribution.

Q: Are these results forecasts?
A: No. They are scenarios. The data is synthetic, the pool and the take rate are assumptions, and an intervention would need to be tested, which is Phase 8.

---

## Phase 6-3: Financial report

Q: What is the main message of Phase 6?
A: Transaction value is not revenue, and most unrecovered value is not retry-addressable. Limits hold 27 percent of unrecovered value from 400 journeys, and the revenue effect of retry gains is small at a realistic take rate.

Q: Why is recovery by value lower than by count?
A: The largest payments fail most often on limits and rarely recover, so recovery by value is 26.1 percent against 32.4 percent by count.

Q: Why does the report call the revenue case weak?
A: At a 0.5 percent take rate, a 10 point recovery gain is about 15,700 rupees over six months. The justification is customer experience and reliability.
Interview angle: "I reported that the revenue case is small, and argued for the work on other grounds."

Q: What do the intervals show?
A: Sampling uncertainty only. They do not show whether the assumed gain can be achieved, which is why the scenarios are tested in Phase 8.

---

## Phase 7-1: Rules layer and duplicate-debit detector

Q: What are the five decisions?
A: Eligible for retry evaluation, Customer action required, Wait for status confirmation, Escalate, Do not retry. They come from the retry class of the first error, whether the status is certain, and whether the bank is having an incident.

Q: Why is a timeout never retried straight away?
A: A timeout does not prove the payment failed. The bank may already have debited the customer, so a retry could charge twice. Timeouts and pending attempts go to Wait for status confirmation.
Interview angle: "The first rule I wrote was the one that prevents harm, and I audited that it never fires wrongly."

Q: Why is there a hard-rule audit with zero counts?
A: A safety rule is only credible if a query proves it holds. Check 03 counts violations, and all counts must be zero.

Q: How does the incident hold work?
A: A bank and 3-hour block is held when its failure rate is far above normal, measured with a Wilson lower bound so small samples do not trigger it. Retries during an outage mostly fail, so waiting is better. The version here uses hindsight, so a live system would detect incidents later.

Q: How is the duplicate-debit detector built without the answer key?
A: It flags an attempt that settled at the bank after an earlier attempt in the same journey was not an app success but did settle. That means the customer was debited, saw no success, and paid again. The truth column is used only to score it.

Q: Why does the detector miss some cases and raise some false alarms?
A: It cannot see a debit that is still PENDING at the bank, so those are missed. Random settlement flips and merged repeat purchases look like double charges, so they raise false alarms.

Q: Why is the observed recovery by decision not a forecast?
A: Only customers who chose to retry produce an outcome. A retry triggered by the system could behave differently, which is why Phase 8 tests it.

---

## Phase 7-2: Scoring model and policy simulation

Q: Why evaluate on a time split?
A: A model fitted on April to July and tested on August to September has never seen the test period. A random split would let it learn from the same weeks it is tested on and flatter it.

Q: How can a model improve on the rules if the rules already decide?
A: The rules decide which journeys may be retried, but give no ranking inside that group. The model's value is in ordering the Eligible group, measured by top-decile lift. If lift is near 1, the rules are enough.
Interview angle: "I judged the model against the rules, and the report says whether it earned its place."

Q: What does calibration show?
A: Whether a predicted 40 percent recovery means about 40 percent actually recovered. A model can rank well and still be badly calibrated.

Q: Why is the policy simulation a counterfactual?
A: Recovery is only observed for customers who chose to retry. The simulation assumes a system retry succeeds at that observed rate, and it counts only journeys the customer never retried. A real system-triggered retry could behave differently, which is why Phase 8 tests it.

Q: Why does retry-everything cause double charges?
A: Some failed or pending journeys were already debited. Retrying them and succeeding charges the customer twice. The rules layer holds those back, and the simulation puts a number on the difference.

Q: Why compare incident thresholds?
A: The first rule flagged blocks at other banks, so precision was 48 percent. Stricter thresholds trade recall for precision. The comparison uses the same data that set the thresholds, so the best variant is optimistic.

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

