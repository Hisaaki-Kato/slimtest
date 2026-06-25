# sample_dbt_project

A small, self-contained dbt project that doubles as the canonical
example for `lighttest`. The domain is an e-commerce order lifecycle so
the sample stands on its own, with no references to any private
codebase. All input data ships in `seeds/` so the project is
reproducible from a clone — no external warehouse tables required.

## Layout

```
sample_dbt_project/
├─ dbt_project.yml                           # model-paths includes target/lighttest
├─ profiles.yml                              # DuckDB profile (local, file-based)
├─ README.md
├─ seeds/                                    # raw input data, CSV-based
│  ├─ order_events.csv
│  ├─ orders.csv
│  ├─ customers.csv
│  └─ products.csv
├─ tests/
│  └─ lighttest_factories/                   # one file per upstream model
│     ├─ order_events.yml
│     ├─ orders.yml
│     ├─ customers.yml
│     └─ products.yml
└─ models/
   └─ marts/
      ├─ order_statuses.sql                  # JOINs all 4 seeds directly
      └─ order_statuses.yml                  # unit tests under meta.lighttest
```

## The model under test

`order_statuses` joins four upstream tables directly:

```
order_events ─┐
              ├─ orders ─┬─ customers
              │          └─ products
              └─ → status intervals (status, valid_from, valid_to)
```

This is intentional — exposing four upstreams in `given:` is exactly
the verbosity dbt's native `unit_tests` makes painful, and is where
lighttest's factories + traits + upstream auto-fill earn their keep.

## Factory model

`lighttest`'s factories are inspired by Ruby's `factory_bot`:

- **One factory per upstream model**. File `tests/lighttest_factories/<upstream>.yml`
  defines factory `<upstream>` whose `base` is "what one sensible row of
  that table looks like".
- **`base`**: common defaults shared by every variant.
- **`traits`**: named diffs that overlay `base` to represent state /
  variant. The `order_events` factory uses traits to switch
  `event_type` (`placed`, `paid`, `shipped`, ...). `customers` uses
  traits to switch `tier` and `country` (`premium`, `us`).
- **`override`**: per-test, per-row diff applied on top of base + trait.
  Use it for IDs and other per-test-unique values.

The naming convention `factory_name == upstream_name` matters: when a
test doesn't mention an upstream in `given:`, lighttest looks for a
factory with that exact name and auto-injects its base row (design.md
§6.5). That's what lets the lifecycle test below specify only
`order_events` — `orders` / `customers` / `products` are stitched in
automatically.

(For readers coming from RSpec: factories are orthogonal to the test
framework. RSpec organises and runs tests; factory_bot constructs test
data; the two are typically used together. In `lighttest`, dbt's
`unit_test` plays the runner role and these factories play the
data-construction role.)

## A test case, end to end

```yaml
# models/marts/order_statuses.yml
- name: status_transitions_through_lifecycle
  given:
    order_events:
      - factory: order_events
        trait: placed
        override: {event_id: 1, occurred_at: '2024-01-01 09:00:00'}
      - factory: order_events
        trait: paid
        override: {event_id: 2, occurred_at: '2024-01-01 09:30:00'}
      - factory: order_events
        trait: shipped
        override: {event_id: 3, occurred_at: '2024-01-02 14:00:00'}
      - factory: order_events
        trait: delivered
        override: {event_id: 4, occurred_at: '2024-01-04 11:00:00'}
  expect:
    - {status: pending,    valid_from: '2024-01-01 09:00:00', valid_to: '2024-01-01 09:30:00'}
    - {status: processing, valid_from: '2024-01-01 09:30:00', valid_to: '2024-01-02 14:00:00'}
    - {status: shipping,   valid_from: '2024-01-02 14:00:00', valid_to: '2024-01-04 11:00:00'}
    - {status: completed,  valid_from: '2024-01-04 11:00:00', valid_to: null}
```

Notice:

- Each `given` row carries only `event_id` + `occurred_at` (not the
  other 3 columns of `order_events`).
- `orders`, `customers`, `products` aren't mentioned at all — auto-fill
  injects one base row of each so the JOIN succeeds.
- `expect` lists only `status`, `valid_from`, `valid_to` — the
  columns this test actually asserts about. dbt's `unit_test` ignores
  any column not present in the expect row.

## What the four tests assert

| Test | Asserts |
|---|---|
| `status_transitions_through_lifecycle` | placed/paid/shipped/delivered emit the four expected statuses with correct interval boundaries |
| `cancellation_after_payment` | a cancelled event terminates the lifecycle with an open-ended `cancelled` interval |
| `returned_after_delivery` | a returned event after delivery emits a 5th `returned` interval |
| `passes_through_order_and_customer_fields` | order_id / customer_id / country / product_category are preserved on the emitted intervals |

## Running

```bash
pip install dbt-core dbt-duckdb              # one-time
cd examples/sample_dbt_project

DBT_PROFILES_DIR=. dbt seed                  # load CSVs into a local *.duckdb file
DBT_PROFILES_DIR=. dbt run                   # materialize order_statuses

# expand only:
uv run --project ../.. lighttest compile --project-dir .

# full flow (dbt parse + compile + dbt test --select <generated names>):
uv run --project ../.. lighttest unittest --project-dir .
```

`dbt run` is required before any unit-test command (lighttest or
otherwise): dbt unit tests introspect the upstream model to learn its
column types, so the relation has to exist first.

`lighttest unittest` exits 0 when all tests pass, 1 otherwise. Failures
are printed with the source location (`models/marts/order_statuses.yml:<line>`)
so you can jump back to the test you wrote.
