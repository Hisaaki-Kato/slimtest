# slimtest

> Factory + trait DSL for dbt™'s `unit_tests`. Removes column-level repetition from your test YAML so the tests stay readable as the upstream schema grows.

`slimtest` is **not** a replacement for `dbt test` — it's a thin pre-processor that lets you write `unit_tests` in a far more compact form, then compiles them into the standard YAML dbt already knows how to run.

```
your factory + trait YAML
        │
        │  $ slimtest compile
        ▼
target/slimtest/<model>.generated.yml   ── standard dbt unit_tests
        │
        │  $ dbt test --select <generated names>     (slimtest unittest does this for you)
        ▼
results (with failures mapped back to your source line)
```

## Why

dbt's built-in `unit_tests` (dbt 1.8+) ask you to spell out every upstream row in full. With wide denormalized tables, or models that join several upstreams, the YAML gets verbose fast — the pain is the **column × row** repetition inside each test, not the number of tests.

`slimtest` lets you say "this is what a row of `customers` normally looks like; in this test, override the tier", instead of typing the same 15 columns into every row.

### Tiny taste

```yaml
# Before: dbt-native unit_tests. One of four upstream blocks shown.
unit_tests:
  - name: test_full_lifecycle
    model: order_statuses
    given:
      - input: ref('order_events')
        rows:
          - {event_id: 1, order_id: 5001, event_type: placed,
             occurred_at: '2024-01-01 09:00:00', cancelled_at: null}
          - {event_id: 2, order_id: 5001, event_type: paid,
             occurred_at: '2024-01-01 09:30:00', cancelled_at: null}
          # ...two more rows, each with the same 5 columns...
      - input: ref('orders')
        rows:
          - {order_id: 5001, customer_id: 8001, product_id: 3001,
             total_amount: 12000, currency: JPY, channel: web,
             placed_at: '2024-01-01 09:00:00', cancelled_at: null}
      - input: ref('customers')
        rows:
          - {customer_id: 8001, country: JP, tier: standard,
             signup_source: organic}
      - input: ref('products')
        rows:
          - {product_id: 3001, category: apparel, price: 12000}
    expect:
      rows:
        - {order_id: 5001, customer_id: 8001, country: JP,
           product_category: apparel, total_amount: 12000,
           currency: JPY, status: pending,
           valid_from: '2024-01-01 09:00:00',
           valid_to: '2024-01-01 09:30:00'}
        # ...three more rows...
```

```yaml
# After: slimtest. Same assertion, every row carries only what changes.
models:
  - name: order_statuses
    meta:
      slimtest:
        unit_tests:
          - name: test_full_lifecycle
            given:
              order_events:
                - {factory: order_events, trait: placed,    override: {event_id: 1, occurred_at: '2024-01-01 09:00:00'}}
                - {factory: order_events, trait: paid,      override: {event_id: 2, occurred_at: '2024-01-01 09:30:00'}}
                - {factory: order_events, trait: shipped,   override: {event_id: 3, occurred_at: '2024-01-02 14:00:00'}}
                - {factory: order_events, trait: delivered, override: {event_id: 4, occurred_at: '2024-01-04 11:00:00'}}
              # orders / customers / products are auto-filled from each factory's base row
            expect:
              - {status: pending,    valid_from: '2024-01-01 09:00:00', valid_to: '2024-01-01 09:30:00'}
              - {status: processing, valid_from: '2024-01-01 09:30:00', valid_to: '2024-01-02 14:00:00'}
              - {status: shipping,   valid_from: '2024-01-02 14:00:00', valid_to: '2024-01-04 11:00:00'}
              - {status: completed,  valid_from: '2024-01-04 11:00:00', valid_to: null}
```

…plus a one-time `tests/slimtest_factories/order_events.yml`:

```yaml
factories:
  order_events:
    base:
      event_id: 10000
      order_id: 5001
      occurred_at: '2024-01-01 09:00:00'
      cancelled_at: null
    traits:
      placed:    {event_type: placed}
      paid:      {event_type: paid}
      shipped:   {event_type: shipped}
      delivered: {event_type: delivered}
      cancelled: {event_type: cancelled}
      returned:  {event_type: returned}
```

The full runnable version of this lives in [`examples/sample_dbt_project/`](examples/sample_dbt_project/).

## Install

Recommended — install as a tool managed by `uv`:

```bash
uv tool install slimtest
```

Or as a dev dependency of your dbt project:

```bash
uv add --dev slimtest
# or, with pip:
pip install slimtest
```

(Until the package is published, replace `slimtest` with the path to a local clone: `uv tool install /path/to/slimtest`.)

## Dependencies

| Layer        | Required                                                       |
| ------------ | -------------------------------------------------------------- |
| Python       | 3.11+                                                          |
| Runtime libs | `pydantic >=2.6,<3`, `ruamel.yaml >=0.18,<1`, `typer >=0.12,<1` |
| dbt          | `dbt-core >=1.10` + an adapter — provided by *your* dbt project, **not** bundled with `slimtest` |

`slimtest` shells out to whatever `dbt` is on `PATH`. Install the dbt adapter that matches your project (`dbt-duckdb`, `dbt-bigquery`, …).

## Quick start

Assuming you already have a dbt project:

1. Tell dbt to read the generated YAML — add `target/slimtest` to `model-paths` in `dbt_project.yml`:

   ```yaml
   model-paths: ["models", "target/slimtest"]
   ```

2. Add a factory at `tests/slimtest_factories/customers.yml`:

   ```yaml
   factories:
     customers:
       base:
         customer_id: 1
         country: JP
         tier: standard
       traits:
         premium: {tier: premium}
   ```

3. Write the test under `meta.slimtest` in your `model.yml`:

   ```yaml
   models:
     - name: dim_customers
       meta:
         slimtest:
           unit_tests:
             - name: premium_tier_propagates
               given:
                 customers:
                   - {factory: customers, trait: premium, override: {customer_id: 42}}
               expect:
                 - {customer_id: 42, tier: premium}
   ```

4. Run it from your dbt project root:

   ```bash
   dbt seed && dbt run    # upstreams must exist before unit tests can introspect their schema
   slimtest unittest
   ```

Failures look like this — note the source location pointing back to the YAML you wrote:

```
[slimtest] 0/1 passed; 1 failed, 0 errored, 0 skipped.
  FAIL: premium_tier_propagates  (models/dim_customers.yml:5)
      actual differs from expected:
      @@ ,customer_id,tier
      → ,42         ,standard→premium
```

For a more complete example with four upstreams and four scenarios, see [`examples/sample_dbt_project/`](examples/sample_dbt_project/).

## Core concepts

### Factory

One factory represents "one row of upstream model X". By convention the factory **name matches the upstream name** so `slimtest` can auto-fill missing upstreams (see below). Factories live in `tests/slimtest_factories/*.yml`.

### `base` and `traits`

- **`base`**: the "default row" — common defaults shared by every variant.
- **`traits`**: named diffs that overlay `base` to represent state / variant (`premium` user, `placed` event, `us` customer, …).

In a test, you reference a row as `{factory: <name>, trait: <name>, override: {...}}`. Layers are **deep-merged** in this order: `base → trait → override`.

### `override`

Per-row, per-test diff applied on top of `base + trait`. This is where test-specific IDs and per-case values go.

### Upstream auto-fill

If a test's `given:` omits an upstream and a factory with the same name exists, `slimtest` injects one `base` row of that factory automatically. A happy-path test that only cares about events doesn't have to repeat the boilerplate of orders / customers / products / etc.

### Scenario

A reusable bundle of `given:` rows declared under `meta.slimtest.scenarios.<name>`. Tests reference it with `scenario: <name>` and `slimtest` merges its `given:` into the test's (test wins per upstream key). Used to factor out "all the supporting rows for one order shape" so tests only carry their differing bits.

```yaml
meta:
  slimtest:
    scenarios:
      premium_jp_books:
        given:
          orders:    [{factory: orders, override: {order_id: 5002}}]
          customers: [{factory: customers, trait: premium, override: {customer_id: 8002}}]
          products:  [{factory: products, trait: books}]
    unit_tests:
      - name: cancellation_after_payment
        scenario: premium_jp_books     # orders/customers/products provided by the scenario
        given:
          order_events: [...]
        expect: [...]
```

### Parametrize

A table-driven sugar that expands one test into N by substituting `$<column>` placeholders. Reduces "for each event type, the status maps to X" style tests from N copies to 1 block.

```yaml
unit_tests:
  - name: event_maps_to_status
    parametrize:
      columns: [event_trait, expected_status]
      cases:
        - [placed,    pending]
        - [paid,      processing]
        - [shipped,   shipping]
        - [delivered, completed]
    given:
      order_events:
        - {factory: order_events, trait: $event_trait, override: {event_id: 1}}
    expect:
      - {status: $expected_status}
```

Each case becomes a separate dbt unit test named `slimtest__<model>__event_maps_to_status__<case_id>`. `case_id` defaults to the first column's value (so the example yields `__placed`, `__paid`, `__shipped`, `__delivered`); set an explicit `id:` column to override.

### Source map

Failures from `dbt test` are mapped back to the source `model.yml` line where you wrote the test, so you don't have to grep through generated YAML.

### Test name prefix

Every generated test is named `slimtest__<model>__<original_name>`, guaranteeing no collision with hand-written `unit_tests` in the same project.

## Coverage

`slimtest` is a wrapper around dbt's **`unit_tests`** feature. It does not replace `dbt test`; it generates the YAML that `dbt test` consumes.

| Test kind                                      | Handled by    | `slimtest` covers?               |
| ---------------------------------------------- | ------------- | --------------------------------- |
| Unit tests (dbt 1.8+ `unit_tests:`)            | `slimtest`   | ✅                                |
| Existing top-level `unit_tests:` (dbt-native)  | dbt           | passthrough (untouched)           |
| Data tests (`unique`, `not_null`, etc.)        | dbt           | ❌ — run `dbt test` directly      |
| Singular tests (`tests/*.sql`)                 | dbt           | ❌ — run `dbt test` directly      |
| Snapshot / seed / macro tests                  | (none)        | ❌ — dbt itself does not support these |

### Currently supported

- factory + trait + override with deep-merge semantics
- `given:` dict form (`{upstream: [rows]}`) instead of dbt's list-of-pairs form
- `model:` field inferred from the enclosing `models[*].name`
- `scenario:` — shared `given:` bundle declared under `meta.slimtest.scenarios`
- `parametrize:` — `$column` substitution that expands one test into N
- `ref()` vs `source()` automatic disambiguation via `manifest.json`
- upstream auto-fill via same-named factories
- partial `expect:` — only list the columns you care about; dbt ignores unmentioned columns
- source map: failure → `models/foo.yml:42`
- `--select` accepts a model name, the user-written test name, the prefixed test name, `test_type:unit`, or a comma-separated union
- works with any dbt adapter (validated on DuckDB; BigQuery and Postgres are mechanically the same)
- `slimtest.yml` config file with `factories_path`, `generated_yml_path`, `auto_fill_upstreams`

### Not yet supported

- `slimtest validate` subcommand (factory / model.yml lint)
- `slimtest factories list`
- factory composition (one row built from multiple factories)
- factory inheritance (one factory extends another)
- stale generated-yml detection (no source-hash invariant yet)
- ephemeral upstreams that require `format: sql` fixtures
- watch mode / IDE integration / LSP completion
- dbt's `dbtRunner` in-process API (we shell out to `dbt`, so each `unittest` pays the dbt cold-start cost)

## Commands

```
slimtest compile  [--project-dir DIR] [--select SEL]
    Expand slimtest extension YAML into target/slimtest/*.generated.yml.
    Does NOT invoke dbt. Useful for debugging the expansion.

slimtest unittest [--project-dir DIR] [--select SEL]
    1. dbt parse        (refresh target/manifest.json)
    2. slimtest compile
    3. dbt test --select <generated test names>
    4. Map failures back to source location.

slimtest --version
slimtest --help
```

The `--select` selector accepts:

- a model name (`orders`)
- a user-written test name (`premium_tier_propagates`)
- a prefixed name (`slimtest__orders__premium_tier_propagates`)
- `test_type:unit` (no-op; everything `slimtest` emits is a unit test)
- comma-separated tokens (`orders,customers`)

## Development

```bash
uv sync                    # install runtime + dev deps into .venv
uv run pytest              # run the test suite
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy src tests      # type check
```

Conventions:

- `ruff` with line-length 88 (E501 is a hard error)
- `mypy --strict` on `src/`; tests are checked with `disallow_untyped_defs` off
- `pydantic` v2 models for every user-facing schema; runtime data is plain `dict[str, Any]`
- dbt is mocked in pytest so the test suite needs no warehouse and no installed adapter

## License

MIT. See [`LICENSE`](LICENSE).

`slimtest` is an independent open-source project and is not affiliated with dbt Labs. `dbt` is a trademark of dbt Labs, LLC.
