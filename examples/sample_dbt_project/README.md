# sample_dbt_project

A small, self-contained dbt project that exercises every `slimtest` feature end-to-end. All input data ships in `seeds/` so the project is reproducible from a clone — no external warehouse required.

If you've read the [project README](../../README.md), this is the runnable version of the snippets there.

## Layout

```
sample_dbt_project/
├─ dbt_project.yml                          # model-paths includes target/slimtest
├─ profiles.yml                             # DuckDB profile (local, file-based)
├─ seeds/                                   # raw input data, CSV-based
│  ├─ order_events.csv
│  ├─ orders.csv
│  ├─ customers.csv
│  └─ products.csv
├─ tests/
│  └─ slimtest_factories/                   # one file per upstream
│     ├─ order_events.yml
│     ├─ orders.yml
│     ├─ customers.yml
│     └─ products.yml
└─ models/
   └─ marts/
      ├─ order_statuses.sql                 # JOINs all 4 seeds directly
      └─ order_statuses.yml                 # tests + scenarios under meta.slimtest
```

## What this sample shows

`order_statuses` joins four upstream tables in one model:

```
order_events ─┐
              ├─ orders ─┬─ customers
              │          └─ products
              └─ → status intervals (status, valid_from, valid_to)
```

A multi-upstream mart is exactly where `slimtest` earns its keep. Five test definitions exercise every feature; `parametrize` further expands one of them into four, so the suite runs as **8 dbt unit tests**.

| Test in source                                  | Demonstrates                                                                 |
| ----------------------------------------------- | ---------------------------------------------------------------------------- |
| `status_transitions_through_lifecycle`          | **upstream auto-fill** — only `order_events` is in `given:`; the other three upstreams are stitched in from their factory bases |
| `event_maps_to_status` (× 4 cases)              | **parametrize** — one block expands to 4 dbt tests via `$column` substitution |
| `cancellation_after_payment`                    | **scenario** — supporting upstreams pulled in from `scenarios.premium_jp_books` |
| `returned_after_delivery`                       | **scenario** + 5-step event stream (`scenarios.us_electronics`)              |
| `passes_through_order_and_customer_fields`      | **partial expect** — verifies only the columns this test cares about         |

## Adapting the pattern to your project

1. **One factory file per upstream**, named after the table: `tests/slimtest_factories/<upstream>.yml`. Factory name matches the upstream name so auto-fill can find it. `base` carries defaults that join correctly across factories (matching IDs); `traits` encode reusable state/variant.
2. **Tests under `meta.slimtest.unit_tests`** in your `model.yml`. `given:` is a dict (`{upstream: [rows]}`), not dbt's list-of-pairs. Each row is `{factory, trait, override}`.
3. **Common setup under `meta.slimtest.scenarios`** — when several tests share the same "what one order/customer/product looks like" wiring, define it once as a scenario and reference it by name.
4. **Table-shaped tests under `parametrize`** — for "input shape × output shape" tables, declare `columns:` + `cases:` once and the block expands to N dbt tests.
5. **`model-paths` includes `target/slimtest`** in `dbt_project.yml` so dbt picks up the generated test YAML.

## Running

```bash
pip install dbt-core dbt-duckdb            # one-time
cd examples/sample_dbt_project

DBT_PROFILES_DIR=. dbt seed                # load CSVs
DBT_PROFILES_DIR=. dbt run                 # materialize order_statuses

uv run --project ../.. slimtest unittest --project-dir .
```

`dbt run` is required before any unit-test command (slimtest or otherwise): dbt's unit tests introspect the upstream model to learn its column types, so the relation has to exist first.

A passing run looks like:

```
[slimtest] compiled 8 test(s)
[slimtest] warning: auto-injected base row of factory 'orders' for upstream 'orders' in test 'slimtest__order_statuses__status_transitions_through_lifecycle' (not present in `given`)
[slimtest] warning: auto-injected base row of factory 'customers' for upstream 'customers' in ...
[slimtest] warning: auto-injected base row of factory 'products' for upstream 'products' in ...
[slimtest] 8/8 passed; 0 failed, 0 errored, 0 skipped.
```
