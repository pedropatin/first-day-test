-- Q4. Daily estimated AI cost by account.
-- ai_cost_usd sums only reported costs. ai_cost_usd_estimated fills the
-- gaps: interactions missing cost_usd are imputed as total_tokens x the
-- model's observed cost-per-token. uncosted_interactions shows how many
-- rows were imputed, so the estimate's completeness is visible.

select
    event_date,
    account_id,
    account_name,
    round(ai_cost_usd, 4) as ai_cost_usd,
    round(ai_cost_usd_estimated, 4) as ai_cost_usd_estimated,
    ai_interactions,
    uncosted_interactions
from gold.daily_account_metrics
where ai_interactions > 0
order by event_date, ai_cost_usd desc;
