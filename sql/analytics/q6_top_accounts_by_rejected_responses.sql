-- Q6. Top accounts by rejected responses.
-- Definition: count of response_rejected events. rejection_rate compares
-- against explicit accept/reject decisions (accepted + rejected), not all
-- AI responses, since many responses receive no explicit decision event.

select
    events.account_id,
    accounts.account_name,
    count(*) filter (event_name = 'response_rejected')  as rejected_responses,
    count(*) filter (event_name = 'response_accepted')  as accepted_responses,
    round(
        100.0 * count(*) filter (event_name = 'response_rejected')
        / nullif(count(*), 0), 1
    ) as rejection_rate_pct
from staging.stg_events as events
left join marts.dim_accounts as accounts using (account_id)
where event_name in ('response_rejected', 'response_accepted')
group by events.account_id, accounts.account_name
order by rejected_responses desc;
