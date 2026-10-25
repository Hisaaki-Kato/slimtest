# Architecture

## Purpose

slimtest removes row-level repetition from dbt unit-test YAML without
replacing dbt. It adds a compact authoring layer and compiles that layer into
the standard `unit_tests` representation dbt already executes.

The primary architectural choice is separation of responsibilities:

- slimtest owns its compact DSL, validation, expansion, artifact publication,
  selection of generated tests, and mapping results back to source locations.
- dbt owns project parsing, model dependency semantics, SQL compilation,
  adapter behavior, and unit-test execution.

## Inputs and outputs

User-controlled inputs are:

- `slimtest.yml`, which configures factory and generated-artifact paths,
  upstream auto-fill, and project-wide dbt unit-test overrides;
- `tests/slimtest_factories/**/*.yml`, which defines reusable input rows;
- `models/**/*.yml`, which contains `models[*].meta.slimtest` blocks;
- the dbt project and its manifest, which provide model and dependency
  identity.

slimtest publishes these build artifacts under the configured generated path,
which defaults to `target/slimtest/`:

- one `<model>.generated.yml` file per model with slimtest tests;
- `source_map.json`, which maps generated logical test names to their
  user-authored source locations;
- `.slimtest-artifacts.json`, which records the generated YAML files owned by
  slimtest.

Generated files are disposable. The compact model YAML and factory YAML remain
the source of truth.

## Compile flow

`slimtest compile` follows this data flow:

1. Load `slimtest.yml`, using schema defaults when it is absent.
2. Load all factory files into a project-wide registry.
3. Discover `meta.slimtest.unit_tests` under the dbt model paths.
4. Validate the user-facing shapes with Pydantic while preserving source line
   information from ruamel.yaml.
5. Expand parametrized cases.
6. Apply scenario data and merge overrides.
7. Resolve factory rows as `base -> trait -> override` and optionally inject
   same-named factory bases for omitted upstreams.
8. Resolve upstream identities through the dbt manifest when one is
   available.
9. Render standard dbt `unit_tests` YAML and the source map.
10. Publish the complete artifact set as one rollback-capable operation.

Selection controls which generated logical test names the caller will run or
report. It does not reduce the complete generated artifact set written by a
compile.

## Unit-test execution flow

`slimtest unittest` adds dbt orchestration around compilation:

1. Temporarily hide slimtest-owned generated YAML so stale files cannot break
   the initial dbt parse.
2. Remove the previous manifest and run `dbt parse`.
3. Stop immediately if parsing fails.
4. Compile using the fresh manifest and publish the replacement artifact set.
5. Remove previous manifest and run-results artifacts for a non-empty test
   selection.
6. Run `dbt test` for the selected generated logical names.
7. Reconcile the fresh manifest and `run_results.json` with the selected test
   set.
8. Map outcomes back to the source model YAML and line number.

Missing, duplicate, unexpected, or unknown dbt results are integrity errors;
they are not treated as successful or silently ignored.

## Design boundaries

- slimtest shells out to the dbt executable supplied by the host project. It
  does not depend on dbt-core as a Python library.
- Generated test names use `slimtest__<model>__<name>` to avoid collisions
  with hand-written dbt unit tests.
- Existing top-level dbt `unit_tests` remain dbt-owned and can coexist with
  `meta.slimtest.unit_tests`.
- slimtest preserves dbt identities rather than flattening every input to a
  bare model name. Sources, package-qualified refs, and model versions remain
  distinguishable.
- Failures should point to user-authored YAML, not require users to inspect
  generated YAML.
