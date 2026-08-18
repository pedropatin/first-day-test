-- Q3. Median and p95 latency by model (continuous, interpolated percentiles).

select
    model,
    count(*)                               as interactions,
    round(median(latency_ms))              as median_latency_ms,
    round(quantile_cont(latency_ms, 0.95)) as p95_latency_ms
from {{ ref('fact_ai_interactions') }}
group by model
order by interactions desc
