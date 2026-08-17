-- Q4. Daily estimated AI cost by account.
-- Definition: sum of known cost_usd on ai_response_generated events.
-- Interactions missing cost_usd contribute 0; uncosted_interactions shows
-- how many were missing so the estimate's completeness is visible.

select
    event_date,
    account_id,
    account_name,
    round(ai_cost_usd, 4) as ai_cost_usd,
    ai_interactions,
    uncosted_interactions
from daily_account_metrics
where ai_interactions > 0
order by event_date, ai_cost_usd desc;
