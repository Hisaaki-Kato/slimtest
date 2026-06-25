with events as (
  select * from {{ ref('order_events_enriched') }}
  where order_events__cancelled_at is null
),

events_with_next as (
  select
    *,
    lead(order_events__occurred_at) over (
      partition by order_events__order_id
      order by order_events__occurred_at
    ) as next_occurred_at
  from events
),

statuses as (
  select
    orders__order_id          as order_id,
    orders__customer_id       as customer_id,
    customers__country        as country,
    products__category        as product_category,
    orders__total_amount      as total_amount,
    orders__currency          as currency,
    case order_events__event_type
      when 'placed'    then 'pending'
      when 'paid'      then 'processing'
      when 'shipped'   then 'shipping'
      when 'delivered' then 'completed'
      when 'cancelled' then 'cancelled'
      when 'returned'  then 'returned'
    end                       as status,
    order_events__occurred_at as valid_from,
    next_occurred_at          as valid_to
  from events_with_next
)

select * from statuses
