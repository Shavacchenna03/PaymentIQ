# Transaction Lifecycle (PayFlow)

## Flow
Customer app -> PayFlow -> PSP -> NPCI UPI switch -> Issuer bank (debit) -> Beneficiary bank (credit) -> response back to the app.
Failures can occur at any hop. A timeout does not prove a payment failed: the debit may have happened.

## Definitions
- Attempt: one try at paying. One row in fact_transactions.
- Journey: one intended payment (same customer, payee and amount, attempts within 30 minutes of each other). Contains one or more attempts.
- Attempt states: INITIATED -> PENDING -> SUCCESS or FAILED.
- PENDING attempts unresolved at the end of the reporting window are excluded from the success rate and reported separately.
- Recovered journey: first attempt failed and a later attempt in the same journey succeeded.
- Abandoned journey: first attempt failed and no later attempt succeeded.

## Note
All data in this project is synthetic. Error codes are PayFlow-internal and illustrative, not official NPCI codes.

