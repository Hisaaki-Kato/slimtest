# Feature status

This document is a compact orientation, not a substitute for executable tests
or the public README.

## Supported behavior

- `slimtest compile` and `slimtest unittest`
- factory `base`, named `traits`, and per-row `override`
- deep-merge row semantics
- literal input rows mixed with factory rows
- dictionary-shaped `given`
- inferred `model` from the enclosing dbt model entry
- reusable scenarios
- table-shaped parametrization
- partial expected rows
- dbt unit-test overrides at project, model, scenario, and test scopes
- automatic preservation of `ref`, `source`, package, and version identity
- explicit qualified input expressions
- upstream auto-fill from same-named factory bases
- incremental current-state input through `given.this`
- generated-name isolation through the `slimtest__` prefix
- source-file and source-line mapping for outcomes
- a supported subset of dbt selector set operations
- coexistence with hand-written dbt unit tests

## Not currently supported

- `slimtest validate`
- `slimtest factories list`
- factory inheritance
- composition of multiple factories into one row
- ephemeral inputs that require SQL-format fixtures
- watch mode, IDE integration, or LSP completion
- in-process execution through dbt's Python runner API
- full dbt selector syntax such as graph operators, tags, paths, and wildcards

## Inherited dbt boundaries

slimtest does not broaden what dbt unit tests can execute. Warehouse SQL
semantics, adapter behavior, relation introspection, and the supported dbt
resource types remain dbt concerns.

The sample project must materialize its upstream relations before unit tests
because dbt introspects them for column types. This is why the end-to-end setup
runs `dbt seed` and `dbt run` before `slimtest unittest`.

## Historical design differences

The original `design.md` describes an MVP named `lighttest`, assumes a
BigQuery-only host project, uses membership lifecycle examples, and defers
several features that are now implemented. Treat those statements as design
history. Current code, tests, README, and the sample project define present
behavior.
