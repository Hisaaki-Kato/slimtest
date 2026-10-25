# Documentation rules

## Scope

These rules apply to `README.md`, `examples/`, agent documentation, CLI help
text, and explanatory comments that describe user-visible behavior.

## Current examples

- Use `slimtest`, `meta.slimtest`, `tests/slimtest_factories/`, and
  `target/slimtest/` in current documentation.
- Prefer the order lifecycle in `examples/sample_dbt_project/` for concrete
  examples.
- Do not copy the historical membership, `lighttest`, or BigQuery-only
  examples from `design.md` into current guidance.
- When `design.md` is consulted, translate its design intent to the current
  order-events sample and verify the behavior against code and tests.

## Keep executable and written examples aligned

- A public DSL or CLI change must update the README when it changes what users
  write, run, or observe.
- A sample-project change must keep its README, model YAML, factory YAML, and
  expected output consistent.
- Prefer links to canonical files over duplicating long examples in multiple
  documents.
- Do not use generated files under the sample project's `target/` directory as
  documentation sources.

## State facts at the right confidence level

- Describe implemented behavior as supported only when code and tests support
  it.
- Keep planned behavior separate from current behavior.
- Name inherited dbt limitations as dbt limitations rather than slimtest
  implementation promises.
- Avoid adapter-specific claims unless they are intentionally part of the
  documented contract.

## Agent-document maintenance

- Keep `AGENTS.md` limited to repository-wide rules and routing.
- Put descriptive project facts in `agent/knowledges/`.
- Put normative, testable constraints in `agent/rules/`.
- Do not duplicate a full rule or knowledge section in several files; link to
  its canonical location.
- Update or remove stale guidance when behavior changes.
