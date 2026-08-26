{{ config(materialized='incremental', unique_key='order_id') }}

select
  order_id,
  max(occurred_at) as last_event_at
from {{ ref('order_events') }}
{% if is_incremental() %}
where occurred_at > (select max(last_event_at) from {{ this }})
{% endif %}
group by order_id
