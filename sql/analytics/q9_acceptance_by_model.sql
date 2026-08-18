-- Q9 (extra). Acceptance rate by model — perceived quality, completing the
-- cost/latency/quality trio for model choice.
-- Definition: share of AI responses whose generation event carried
-- accepted = true, out of those where the flag is present (it is missing on
-- ~13% of calls; flagged_calls makes that base explicit).

select
    model,
    count(*)                                as ai_calls,
    count(accepted)                         as flagged_calls,
    count(*) filter (accepted)              as accepted_calls,
    round(100.0 * count(*) filter (accepted) / nullif(count(accepted), 0), 1)
        as acceptance_rate_pct,
    round(avg(cost_usd_estimated), 4)       as avg_cost_usd,
    round(median(latency_ms))               as median_latency_ms
from marts.fact_ai_interactions
group by model
order by acceptance_rate_pct desc;
