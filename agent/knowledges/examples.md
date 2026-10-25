# Example map

## Canonical example vocabulary

Use `examples/sample_dbt_project/` for concrete explanations. It is the
runnable replacement for the membership and BigQuery-specific examples in
the historical `design.md`.

The sample domain is an order lifecycle:

```text
order_events -> orders -> customers
                    \-> products
```

`order_statuses` turns events such as `placed`, `paid`, `shipped`,
`delivered`, `cancelled`, and `returned` into status intervals.

Prefer this vocabulary in agent documentation, tests, issue explanations, and
new README examples unless a different domain is required to reproduce a
specific bug.

## Feature-to-example index

The main source file is
`examples/sample_dbt_project/models/marts/order_statuses.yml`.

| Feature | Canonical example |
| --- | --- |
| Factory, trait, and override | `status_transitions_through_lifecycle` |
| Upstream auto-fill | `status_transitions_through_lifecycle` |
| Parametrization | `event_maps_to_status` |
| Scenario reuse | `cancellation_after_payment` |
| Longer scenario event stream | `returned_after_delivery` |
| Partial expected rows | `passes_through_order_and_customer_fields` |
| Model-level dbt overrides | `applies_model_level_overrides` |
| Test-level override precedence | `test_level_overrides_win` |

Incremental behavior is demonstrated separately in
`examples/sample_dbt_project/models/marts/latest_order_events.yml` by
`processes_only_new_events`, including the reserved `given.this` input.

Factory definitions are split by upstream under
`examples/sample_dbt_project/tests/slimtest_factories/`. The default IDs are
coordinated so auto-filled base rows join successfully.

## What makes an example canonical

A canonical example should:

- run end to end in CI with DuckDB;
- demonstrate one primary concept clearly;
- use factories whose IDs and values join consistently;
- contain enough source data to explain the expected output;
- match the public behavior documented in `README.md`;
- avoid generated files under `target/` as teaching material.

The sample project's README explains how to prepare and run the example. CI
executes dbt seed, dbt run, and `slimtest unittest` against the same project.
