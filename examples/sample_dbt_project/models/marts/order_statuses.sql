with events as (
  select * from {{ ref('order_events') }}
  where cancelled_at is null
),

joined as (
  select
    e.event_id,
    e.order_id,
    e.event_type,
    e.occurred_at,
    o.customer_id,
    o.product_id,
    o.total_amount,
    o.currency,
    c.country,
    c.tier,
    p.category as product_category
  from events e
  left join {{ ref('orders') }}    o on e.order_id    = o.order_id
  left join {{ ref('customers') }} c on o.customer_id = c.customer_id
  left join {{ ref('products') }}  p on o.product_id  = p.product_id
),

events_with_next as (
  select
    *,
    lead(occurred_at) over (
      partition by order_id
      order by occurred_at
    ) as next_occurred_at
  from joined
)

select
  order_id,
  customer_id,
  country,
  product_category,
  total_amount,
  currency,
  case event_type
    when 'placed'    then 'pending'
    when 'paid'      then 'processing'
    when 'shipped'   then 'shipping'
    when 'delivered' then 'completed'
    when 'cancelled' then 'cancelled'
    when 'returned'  then 'returned'
  end                       as status,
  occurred_at               as valid_from,
  next_occurred_at          as valid_to
from events_with_next
