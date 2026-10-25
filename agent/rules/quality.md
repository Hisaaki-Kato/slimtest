# Quality rules

## Test at the owning layer

- Add or update tests for observable behavior changes.
- Prefer focused tests while iterating.
- Cover failures and invalid input, not only the happy path, when the behavior
  validates user data or protects artifacts.
- Use mocked dbt invocations for the normal unit-test suite; do not require a
  warehouse or installed adapter for `tests/`.
- Update the DuckDB sample when a change needs end-to-end dbt coverage.

## Required handoff checks

Before handing off code changes, run the same static and unit-test checks as
CI from the repository root:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
```

Run all four commands even if a focused test already passed. If the task only
changes Markdown, run the checks unless the user explicitly limits validation
or the environment makes them unavailable.

## End-to-end sample check

Run the sample-project flow when changing dbt invocation, manifest handling,
generated YAML, the public DSL, or the sample itself:

```bash
cd examples/sample_dbt_project
uv run --project ../.. --with dbt-duckdb dbt seed \
  --profiles-dir . --profile slimtest_sample --target dev
uv run --project ../.. --with dbt-duckdb dbt run \
  --profiles-dir . --profile slimtest_sample --target dev
uv run --project ../.. --with dbt-duckdb slimtest unittest \
  --project-dir . --profiles-dir . --profile slimtest_sample --target dev
```

The end-to-end check supplements rather than replaces the four required
handoff checks.

## Handoff report

State which checks passed. If any required check could not run or failed for a
reason outside the change, report the exact check and the blocker; do not
describe the change as fully verified.
