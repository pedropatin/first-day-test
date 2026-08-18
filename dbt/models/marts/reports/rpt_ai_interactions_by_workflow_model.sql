-- Q2. Number of AI interactions by workflow and model.
-- An AI interaction = one ai_response_generated event.

select
    workflow,
    model,
    count(*) as ai_interactions
from {{ ref('fact_ai_interactions') }}
group by workflow, model
order by ai_interactions desc
