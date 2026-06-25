# sample_dbt_project

A small, self-contained dbt project that exercises every `lighttest` feature end-to-end. All input data ships in `seeds/` so the project is reproducible from a clone — no external warehouse required.

If you've read the [project README](../../README.md), this is the runnable version of the snippets there.

## Layout

```
sample_dbt_project/
├─ dbt_project.yml                          # model-paths includes target/lighttest
├─ profiles.yml                             # DuckDB profile (local, file-based)
├─ seeds/                                   # raw input data, CSV-based
│  ├─ order_events.csv
│  ├─ orders.csv
│  ├─ customers.csv
│  └─ products.csv
├─ tests/
│  └─ lighttest_factories/                  # one file per upstream
│     ├─ order_events.yml
│     ├─ orders.yml
│     ├─ customers.yml
│     └─ products.yml
└─ models/
   └─ marts/
      ├─ order_statuses.sql                 # JOINs all 4 seeds directly
      └─ order_statuses.yml                 # tests under meta.lighttest
```

## What this sample shows

`order_statuses` joins four upstream tables in one model:

```
order_events ─┐
              ├─ orders ─┬─ customers
              │          └─ products
              └─ → status intervals (status, valid_from, valid_to)
```

A multi-upstream mart is exactly where `lighttest` earns its keep. The four tests demonstrate, in roughly increasing complexity:

| Test                                            | Demonstrates                                                                 |
| ----------------------------------------------- | ---------------------------------------------------------------------------- |
| `status_transitions_through_lifecycle`          | **upstream auto-fill** — only `order_events` is in `given:`; the other three upstreams are stitched in from their factory bases |
| `cancellation_after_payment`                    | overriding factory `base` IDs to wire up a different scenario                |
| `returned_after_delivery`                       | combining traits (`customers` `us`, `products` `electronics`) per row        |
| `passes_through_order_and_customer_fields`      | **partial expect** — verifying only the columns this test cares about        |

## Adapting the pattern to your project

1. **One factory file per upstream**, named after the table: `tests/lighttest_factories/<upstream>.yml`. Factory name matches the upstream name so auto-fill can find it. `base` carries defaults that join correctly across factories (matching IDs); `traits` encode reusable state/variant.
2. **Tests under `meta.lighttest.unit_tests`** in your `model.yml`. `given:` is a dict (`{upstream: [rows]}`), not dbt's list-of-pairs. Each row is `{factory, trait, override}`.
3. **`model-paths` includes `target/lighttest`** in `dbt_project.yml` so dbt picks up the generated test YAML.

## Running

```bash
pip install dbt-core dbt-duckdb            # one-time
cd examples/sample_dbt_project

DBT_PROFILES_DIR=. dbt seed                # load CSVs
DBT_PROFILES_DIR=. dbt run                 # materialize order_statuses

uv run --project ../.. lighttest unittest --project-dir .
```

`dbt run` is required before any unit-test command (lighttest or otherwise): dbt's unit tests introspect the upstream model to learn its column types, so the relation has to exist first.

A passing run looks like:

```
[lighttest] compiled 4 test(s)
[lighttest] warning: auto-injected base row of factory 'orders' for upstream 'orders' in test 'lighttest__order_statuses__status_transitions_through_lifecycle' (not present in `given`)
[lighttest] warning: auto-injected base row of factory 'customers' for upstream 'customers' in ...
[lighttest] warning: auto-injected base row of factory 'products' for upstream 'products' in ...
[lighttest] 4/4 passed; 0 failed, 0 errored, 0 skipped.
```
