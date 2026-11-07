# Ground Truth: Planted Patterns (declared before analysis)

This file is committed before Phase 3 so the Git history proves the patterns were declared first. The test is whether the analysis methods recover the right magnitudes and avoid the traps, not whether they find the patterns.

| ID | Planted pattern | Where it should be found |
|---|---|---|
| P1 | Bank outage: one bank down in 3 short windows (BNK_01 spike) | Phase 3-4 anomaly detection |
| P2 | Peak-hour decay: failures rise 8-10pm. Small and cooperative banks degrade far more than large banks (bank x hour interaction) | Phase 4 |
| P3 | Failure concentration: top 20 percent of banks produce about 60-65 percent of failures. Part is volume, part is real unreliability | Phase 4 Pareto |
| P4 | Simpson's trap: Bank A looks bad raw but is fine after controlling for amount and network. Bank B looks average but is truly bad because it serves easy low-value transactions | Phase 4 regression |
| P5 | Network effect: timeouts about 3x more likely on 3G and 2G | Phase 4 |
| P6 | Amount effect: LIM_02 appears above the per-transaction limit. Risk blocks rise mildly above Rs 10,000 | Phase 3-4 |
| P7 | Bad deploy: one PSP has 2 weeks of PSP_01 errors and rising latency, then recovers | Phase 3-4 change-point |
| P8 | Latency trap: timeouts have high latency by definition, so latency vs failure is partly mechanical, not causal | Phase 3-4 |
| P9 | Null effect: device type has NO true effect on failure | Phase 4. Tests that false findings are not reported |
| P10 | Retry behaviour by code: wrong PIN has high retry and success. Insufficient funds has low retry and success. Limit exceeded rarely recovers | Phase 5-6 |
| P11 | Hidden segments: 5 latent customer types (reliable, retry-dependent, failure-prone, abandoning, high-value) | Phase 5 |
| P12 | Ambiguous timeouts: about 1 percent of timeouts actually debited the customer. Some customers retry and are charged twice | Phase 7 |
| P13 | Trend: volume grows about 35 percent over 6 months while success rate improves about 1 point, masked by weekday and month-end seasonality | Phase 3 |

## Deliberate data quality issues (all must be logged and cleaned)
- About 0.2 percent of rows with missing latency
- About 0.1 percent duplicate rows
- One PSP writes timestamps in UTC instead of IST
- Some FAILED rows with no error code (mapped to UNK_01)

## Magnitudes
Exact planted magnitudes are stored in the generator config and the truth schema, and are compared with analysis results in the final ground-truth comparison.


## Amendments (Phase 2C-2, committed before any analysis)
- P1: the outage bank is Kestrel Commercial (a Large bank), not a small one, so the windows contain enough payments to detect. Windows are 4 to 5 hours long.
- P3: with the 8 Large banks holding 70 percent of volume, the top 20 percent of banks produce about 66 to 70 percent of failures, not 60 to 65. Most of that is volume. The Pareto chart must be read against volume share, and the real finding is which banks fail more than their volume predicts.
- P5: timeouts and network failures are about 3.3 times more likely on 3G and 4.5 times on 2G, relative to WiFi and 5G.
- P4: the network family is the largest failure family (about 4 percent of attempts) so that Tarang National looks worse in raw data and is cleared after controlling for network.

## Amendments (Phase 2C-3a, committed before any analysis)
- P8: timeouts have fixed long latencies (NET_01 about 30 s, NET_03 about 20 s, NET_02 about 8 s median, BNK_04 about 12 s), so high latency predicts failure mechanically. Latency also rises on weaker networks (2G about 3.3x WiFi) and at smaller banks (Medium 1.1x, Small 1.25x), so latency and failure also share the network confounder.
- P7: Clearwave latency on non-timeout attempts ramps linearly from 1.0x on 3 Aug to 2.0x on 16 Aug, and returns to normal on 17 Aug.
- P12: 3 percent of timeout failures were really debited. This is inflated from the original 1 percent so the Phase 7 duplicate-charge analysis has enough events. A real-world rate would be lower. Double charges are created in 2C-3b.
- PENDING: about 0.5 percent of attempts, mostly from uncertain-status codes (timeouts, BNK_04, UNK_02).
- LIM_01: only 4 failures in the generated data. It is negligible and will not be analysed.
