-- Q2. Number of AI interactions by workflow and model.
-- Definition: an AI interaction = one ai_response_generated event
-- (fact_ai_interactions grain).

select
    workflow,
    model,
    count(*) as ai_interactions
from marts.fact_ai_interactions
group by workflow, model
order by ai_interactions desc;
