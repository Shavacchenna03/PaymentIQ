# Failure Taxonomy

Categories are illustrative; a failure cannot always be attributed to a single participant.

| Code | Category | Meaning | Retry class |
|---|---|---|---|
| BNK_01 | Bank-side | Issuer bank unavailable | Safe retry (later) |
| BNK_02 | Bank-side | Issuer technical decline | Verify status first |
| BNK_03 | Bank-side | Insufficient funds | Customer action |
| PSP_01 | PSP-side | PSP processing error | Safe retry |
| PSP_02 | PSP-side | PSP service unavailable | Safe retry (later) |
| NET_01 | Network | Request timeout | Verify status first |
| NET_02 | Network | Connectivity lost mid-request | Verify status first |
| CUS_01 | Customer | Incorrect UPI PIN | Customer action |
| CUS_02 | Customer | PIN attempts exceeded | Customer action |
| CUS_03 | Customer | Customer cancelled | Do not retry |
| LIM_01 | Limit | Daily transaction limit exceeded | Customer action |
| LIM_02 | Limit | Per-transaction limit exceeded | Customer action |
| TEC_01 | Technical | Invalid request format | Do not retry (fix first) |
| TEC_02 | Technical | Duplicate request id | Verify status first |
| RSK_01 | Risk | Blocked by security controls | Do not retry |
| UNK_01 | Unknown | Unclassified error | Escalate |

Retry classes: Safe retry, Customer action, Verify status first, Do not retry, Escalate.
Codes marked "Verify status first" must never be blindly retried: risk of duplicate debit.
Target: extend to 25-40 codes in Phase 2.
