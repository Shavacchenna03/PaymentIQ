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

## Extended codes (Phase 2B)
The database has 28 codes. These 12 were added to the original 16:
BNK_04 Issuer response delayed (Verify status first), BNK_05 Account inactive or frozen (Customer action), BNK_06 Issuer under maintenance (Safe retry), PSP_03 PSP rate limit hit (Safe retry), PSP_04 PSP routing error (Safe retry), NET_03 Gateway timeout (Verify status first), CUS_04 Invalid UPI ID or payee (Customer action), CUS_05 Collect request expired (Customer action), LIM_03 Merchant limit exceeded (Customer action), TEC_03 Auth token expired (Safe retry), RSK_02 Velocity check triggered (Escalate), UNK_02 Status unknown after response (Escalate).
Note: the database stores only the five exact retry class names. Qualifiers such as "(later)" and "(fix first)" from the first table are dropped.
"Do not retry" codes remain CUS_03, TEC_01 and RSK_01, matching the metric dictionary.
