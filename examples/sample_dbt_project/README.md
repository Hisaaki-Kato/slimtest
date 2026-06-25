# sample_dbt_project

A small, self-contained dbt project that reproduces the pain `lighttest`
sets out to solve: verbose dbt `unit_tests` YAML where most columns repeat
unchanged across rows.

The domain is intentionally generic (e-commerce order lifecycle) so the
sample stands on its own, with no references to any private codebase.
All input data ships in `seeds/` so the project is reproducible from a
clone — no external warehouse tables required.

## Layout

```
sample_dbt_project/
├─ dbt_project.yml
├─ profiles.yml                              # DuckDB profile (local, file-based)
├─ README.md
├─ seeds/                                    # raw input data, CSV-based
│  ├─ order_events.csv
│  ├─ orders.csv
│  ├─ customers.csv
│  └─ products.csv
└─ models/
   ├─ intermediate/
   │  ├─ order_events_enriched.sql           # 18-column wide join
   │  └─ order_events_enriched.yml
   └─ marts/
      ├─ order_statuses.sql                  # status-interval model
      └─ order_statuses.yml                  # *** the painful unit tests ***
```

## Models

- `order_events_enriched` — joins `order_events` with `orders`, `customers`
  and `products`. **18 columns** total, named `<table>__<column>` to mirror
  the kind of wide denormalized tables that drive the pain in real
  warehouses.
- `order_statuses` — derived from `order_events_enriched`. Translates the
  event stream into status intervals: `pending` -> `processing` ->
  `shipping` -> `completed` / `cancelled` / `returned`, each with
  `valid_from` and `valid_to`.

## Where the pain lives

Open `models/marts/order_statuses.yml`. It defines three unit tests with
**12 input rows total**, each carrying **18 columns**:

| Test | Scenario | Input rows | Expected rows |
|---|---|---|---|
| `test_full_lifecycle` | placed -> paid -> shipped -> delivered | 4 | 4 |
| `test_cancellation_after_payment` | placed -> paid -> cancelled | 3 | 3 |
| `test_returned_after_delivery` | full lifecycle + returned | 5 | 5 |

Within each test, **15 of the 18 columns hold the exact same value on
every row** (customer_id, country, tier, currency, channel, product_id,
category, price, total_amount, placed_at, etc.). Only `event_id`,
`event_type` and `occurred_at` actually change per row.

That repetition — `O(rows x columns)` typing for `O(rows)` worth of real
intent — is exactly the cost `lighttest` is designed to remove with
factories, traits and overrides.

## Running the tests

```bash
# from the repo root
pip install dbt-core dbt-duckdb        # one-time
cd examples/sample_dbt_project
DBT_PROFILES_DIR=. dbt seed            # load CSVs into a local *.duckdb file
DBT_PROFILES_DIR=. dbt run             # materialize the models
DBT_PROFILES_DIR=. dbt test --select test_type:unit
```

`dbt run` is required before `dbt test`: dbt unit tests introspect the
upstream model to learn its column types, so the relation has to exist
first. (Equivalently, you can run `DBT_PROFILES_DIR=. dbt build` to do
seed → run → test in one shot.)

DuckDB persists the data into `target/lighttest_sample.duckdb` (gitignored).
Unit tests run as `SELECT`s that inject their own rows on top of the
materialized tables, so the seed contents only need to define column
shapes — the unit test bodies provide all the data the assertions check.
