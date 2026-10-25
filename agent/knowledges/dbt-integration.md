# dbt integration

## Manifest responsibilities

slimtest reads `target/manifest.json` to obtain information that belongs to
dbt rather than duplicating dbt's parser:

- the dependencies of each tested model;
- whether an input is a ref-able resource or a source;
- package qualification and model version information;
- the concrete dbt unit-test IDs created from generated logical tests;
- the model targeted by each unit test.

Bare `given` keys are resolved within the tested model's dependency scope
first. If more than one identity remains possible, users must provide an
explicit `ref(...)` or `source(...)` expression. Unknown names fall back to a
bare `ref('<name>')` when compiling without enough manifest information.

## Generated YAML

Generated documents use dbt's top-level `unit_tests` format. For each test,
slimtest emits:

- the prefixed logical name;
- the inferred model name;
- optional description and overrides;
- a list of dbt input expressions and fully expanded rows;
- expected rows.

The configured generated path must be present in the dbt project's
`model-paths`; otherwise compile reports a warning because dbt will not
discover the generated unit tests.

## Selectors

slimtest supports a deliberate subset of dbt selection syntax:

- model name;
- base source test name;
- concrete parametrized test name;
- prefixed generated test name;
- `test_type:unit`;
- whitespace union semantics;
- comma intersection semantics.

Graph operators, wildcard syntax, and other selector methods are rejected
instead of being approximated. A non-empty valid selector that matches no
slimtest test is also an error.

A base parametrized name selects every concrete case. An exact concrete
generated name selects only that case.

## Freshness and result integrity

`slimtest unittest` requires artifacts produced by the current invocation.
Before dbt calls, it removes previous JSON artifacts that could make a failed
or no-op run appear successful.

After `dbt test`, slimtest checks that:

- every selected logical test appears in the fresh manifest;
- every expected dbt unit-test ID has exactly one result;
- no unexpected unit-test result is accepted;
- every result status is recognized.

Versioned dbt models may produce multiple concrete unit-test IDs for one
generated logical name. The fresh manifest maps those IDs back to the same
slimtest source definition.

## Source mapping

`source_map.json` records the source file, source line, generated file, model,
and original unprefixed name for every generated logical test. CLI failure
output uses that mapping so the user sees the test name and location from the
model YAML they authored.

Source location is part of the user experience. Changes to parsing,
parametrization, naming, manifests, or result reconciliation can affect it even
when generated SQL still executes successfully.

## Adapter boundary

The library does not encode warehouse-specific SQL semantics. dbt and the
installed adapter compile and execute the model. The repository's end-to-end
example uses DuckDB because it is local and reproducible, but the slimtest
layer is intended to remain adapter-independent.
