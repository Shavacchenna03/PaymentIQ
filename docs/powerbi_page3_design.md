# Power BI Page 3: Customer Behaviour

Business question: what do customers do after a payment fails, and where is recovery lost?

## Data sources
journey_summary (variant w30b), v_retry_gaps_any, customer_features, v_cohorts, v_cohort_activity, dim_failure_codes.

## Layout
- Cards: first-attempt success rate, retry rate, journey recovery rate, abandonment rate, share of unrecovered journeys never retried.
- Funnel: eligible failed journeys, retried, recovered.
- Bar: recovery rate by first error code, coloured by retry class.
- Histogram: time to retry (log scale), line at 30 minutes.
- Window selector: recovery and merged journeys under w15, w30, w30b, w60.
- Cohort chart: first-failure rate by signup cohort with intervals; activity by month.
- Slicers: signup cohort, city tier, retry class.

## Rules
- Journey metrics are labelled as derived by w30b.
- No customer-segment visual (not recoverable at this sample size); show group means only if explained.
