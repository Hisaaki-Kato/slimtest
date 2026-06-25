with order_events as (
  select * from {{ ref('order_events') }}
),

orders as (
  select * from {{ ref('orders') }}
),

customers as (
  select * from {{ ref('customers') }}
),

products as (
  select * from {{ ref('products') }}
)

select
  order_events.event_id                as order_events__event_id,
  order_events.order_id                as order_events__order_id,
  order_events.event_type              as order_events__event_type,
  order_events.occurred_at             as order_events__occurred_at,
  order_events.cancelled_at            as order_events__cancelled_at,

  orders.order_id                      as orders__order_id,
  orders.customer_id                   as orders__customer_id,
  orders.total_amount                  as orders__total_amount,
  orders.currency                      as orders__currency,
  orders.channel                       as orders__channel,
  orders.placed_at                     as orders__placed_at,

  customers.customer_id                as customers__customer_id,
  customers.country                    as customers__country,
  customers.tier                       as customers__tier,
  customers.signup_source              as customers__signup_source,

  products.product_id                  as products__product_id,
  products.category                    as products__category,
  products.price                       as products__price

from order_events
left join orders     on order_events.order_id = orders.order_id
left join customers  on orders.customer_id    = customers.customer_id
left join products   on orders.product_id     = products.product_id
