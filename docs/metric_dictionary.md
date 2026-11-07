# Metric Dictionary (v1.0, final)

## Global rules
- Reporting window: calendar day in IST. All timestamps stored in one timezone.
- Eligible attempts: terminal state (SUCCESS or FAILED), counted only after a 24-hour settlement lag.
- PENDING attempts after 24h are excluded from rates and reported as Pending Share.
- Customer-cancelled (CUS_03) attempts are excluded from attempt-level success and failure rates.
- "Do not retry" codes: CUS_03, TEC_01, RSK_01.
- Recovery-eligible journey: a failed-first journey whose first error is NOT a "Do not retry" code.

## Attempt-level metrics
| KPI | Numerator | Denominator | Notes |
|---|---|---|---|
| Transaction Success Rate | SUCCESS attempts | SUCCESS + FAILED attempts | Excludes PENDING and CUS_03 |
| Transaction Failure Rate | FAILED attempts | SUCCESS + FAILED attempts | Excludes CUS_03 |
| Technical Failure Rate | FAILED attempts in Bank, PSP, Network, Technical categories | SUCCESS + FAILED attempts | Excludes customer-caused failures. Shown beside the headline failure rate |
| Pending Share | PENDING attempts after 24h | All attempts | Reported separately |
| Average Transaction Value | Sum of SUCCESS amounts | SUCCESS count | |
| P95 Latency | 95th percentile of latency_ms | SUCCESS + FAILED attempts | Also report P50 and P99 |
| Retry Success Rate | Retry attempts that SUCCEED | All retry attempts | Attempt-level |
| Reconciliation Rate | Attempts where final status matches settlement status | Attempts with a reconciliation record | |

## Journey-level metrics
| KPI | Numerator | Denominator | Notes |
|---|---|---|---|
| First-Attempt Success Rate | Journeys whose first attempt is SUCCESS | All journeys | |
| Retry Rate | Failed-first journeys with 2+ attempts | Failed-first journeys | |
| Journey Recovery Rate | Recovery-eligible journeys that end in SUCCESS | Recovery-eligible journeys | Headline recovery metric |
| Abandonment Rate | Recovery-eligible journeys with no SUCCESS | Recovery-eligible journeys | Journey Recovery Rate + Abandonment Rate = 100% |
| Recovery Rate (all failed-first) | Failed-first journeys that end in SUCCESS | All failed-first journeys | Pessimistic view, no exclusion. Shows how much the exclusion changes the result |

## Concentration and financial metrics
| KPI | Numerator | Denominator | Notes |
|---|---|---|---|
| Failure Concentration | Failures from the top 20% of banks | All failures | Pareto view |
| Incremental Recovery Value | Modelled extra recovered amount | n/a | Scenario-based. Labelled hypothetical, not an achieved result |

## Sanity checks
- Journey Recovery Rate + Abandonment Rate must equal 100%.
- Recovery Rate (all failed-first) must be less than or equal to Journey Recovery Rate.
- Success Rate + Failure Rate must equal 100%.
- Journey window is 30 minutes by assumption. Sensitivity tested at 15 and 60 minutes in Phase 5.

## Clarification (Phase 2C-2)
Technical Failure Rate counts failures in the Bank-side, PSP-side, Network and Technical categories, but EXCLUDES BNK_03 (insufficient funds) and BNK_05 (account inactive or frozen). They sit under Bank-side only because the issuer reports them, and they are customer-caused. Limit, Risk and Unknown categories are also outside the Technical Failure Rate.
