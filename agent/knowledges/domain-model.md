# Domain model

## Factory rows

A factory represents one reusable row for a dbt unit-test input. Factory names
are project-wide identifiers and are conventionally the same as their
upstream model or source name.

Each factory contains:

- `base`: the default row and common values;
- `traits`: optional named differences representing meaningful variants.

A test row can then add an `override` for values specific to that test case.
Resolution uses a deep merge in this order:

```text
base -> trait -> override
```

Later layers win. An explicitly provided `null` is a value, not a deletion.
A row without a `factory` key is a literal row and passes through unchanged.

## Tests and inferred models

Tests live under `models[*].meta.slimtest.unit_tests`. The enclosing
`models[*].name` supplies the dbt `model` field, so users do not repeat it in
each test.

`given` is a mapping from an upstream identity to a list of rows. A bare key is
resolved among the enclosing model's manifest dependencies. Explicit forms
such as `ref('package', 'orders', version=2)` and
`source('raw', 'orders')` are accepted when a bare name would be ambiguous.
These expressions are parsed as data; slimtest does not evaluate arbitrary
Python or Jinja.

`expect` contains literal expected rows. It can be partial: dbt compares the
columns present in the expected rows, so a test can state only the behavior it
cares about.

## Scenarios

A scenario is a named bundle of supporting `given` rows under
`meta.slimtest.scenarios`.

When a test references a scenario:

- scenario upstreams absent from the test are added;
- if both scenario and test provide the same upstream key, the test's entire
  row list wins for that key;
- scenario and test override sections are merged separately by key.

Scenarios describe reusable multi-upstream setup. Traits describe reusable
variants of one factory row; the concepts are intentionally separate.

## Parametrization

`parametrize` expands one source test into one concrete test per case. Cases
may be lists paired with a `columns` header or mappings whose keys are the
columns.

Strings of the exact form `$column` in `given` and `expect` are replaced with
the case value. Substrings and arbitrary templates are not evaluated.

Concrete names use `<base-name>__<case-id>`. The case ID is chosen from an
explicit string `id`, then the first string column, then the zero-based case
index. Unsafe characters are normalized for dbt test identifiers.

## Overrides

dbt unit-test `overrides.macros`, `overrides.vars`, and
`overrides.env_vars` remain opaque to slimtest and are passed through for dbt
to interpret.

Each section is merged by key with this precedence:

```text
project < model < scenario < test
```

Higher-precedence keys replace matching lower-precedence keys without
discarding unrelated keys from the same section.

## Upstream auto-fill

When enabled, auto-fill examines manifest dependencies omitted from `given`.
If the factory registry contains a factory with the same dependency name,
slimtest injects one resolved base row and records an informational notice.
Dependencies without a same-named factory remain omitted and therefore retain
dbt's empty-input behavior.

Factory base values used for auto-fill must form a coherent join across the
related upstreams. The sample project coordinates the default order,
customer, product, and event IDs for this reason.

## Incremental input

The reserved `given.this` input represents the current contents of an
incremental model. Its rows support the same literal and factory forms as
other inputs. Expected rows represent the incremental query output that dbt
would insert or merge, not the final materialized table.
