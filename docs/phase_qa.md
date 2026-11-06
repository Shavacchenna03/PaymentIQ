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

## Upcoming sections (added when each phase completes)

Phase 2: Data engineering. Expected topics: schema design, primary and foreign keys, how realistic failures are generated, the ground-truth file, validation checks.
Phase 3: W1 Payment performance. Expected topics: success-rate trends, window functions, P95 in SQL, value-band analysis.
Phase 4: W2 Root cause. Expected topics: Pareto, logistic regression with controls, confounders, correlation versus causation.
Phase 5: W3 Customer journey. Expected topics: sessionisation, funnels, segmentation, cohorts, window sensitivity.
Phase 6: W4 Financial impact. Expected topics: failed versus lost value, revenue-at-risk assumptions, scenario analysis.
Phase 7: W5 Recovery intelligence. Expected topics: rules versus scoring layer, idempotency, duplicate debit, model comparison.
Phase 8: W6 Experimentation. Expected topics: hypothesis, sample size, significance, confidence intervals, guardrail metrics.
Phase 9: Portfolio. Expected topics: telling the project story, defending assumptions, limitations.

