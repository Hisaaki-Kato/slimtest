# Repository instructions

These instructions apply to the entire repository. Keep this file concise: it
contains the rules every agent needs and routes task-specific work to the
relevant project documentation.

## Project overview

slimtest is a Python CLI and YAML preprocessor for dbt unit tests. Users write
compact tests with factories, traits, scenarios, and parametrization under
`meta.slimtest`; slimtest compiles them to standard dbt `unit_tests` YAML and
delegates execution to dbt.

User-authored YAML is the source of truth. Files under `target/slimtest/` are
generated build artifacts and must never become an alternative source of
truth.

## Read only the context the task needs

Do not load every agent document before every change. Read the documents that
match the work:

- System boundaries and compile/run flow:
  `agent/knowledges/architecture.md`
- DSL concepts and precedence:
  `agent/knowledges/domain-model.md`
- dbt manifests, selectors, execution results, and source mapping:
  `agent/knowledges/dbt-integration.md`
- Runnable examples and the preferred concrete vocabulary:
  `agent/knowledges/examples.md`
- Current feature boundaries:
  `agent/knowledges/feature-status.md`
- Release metadata, commits, or pull requests:
  `agent/rules/release.md`
- Generated artifact code or files:
  `agent/rules/generated-artifacts.md`
- Public DSL, CLI, config, generated YAML, or dbt behavior:
  `agent/rules/compatibility.md`
- README, examples, or other user-facing documentation:
  `agent/rules/documentation.md`
- Verification before handoff:
  `agent/rules/quality.md`

`design.md` records the original MVP thinking and includes examples from an
earlier project. Use it for design history, not as the current product
specification. Translate its examples to the order lifecycle in
`examples/sample_dbt_project/`.

## Repository-wide rules

- Preserve unrelated user changes in a dirty worktree.
- Do not hand-edit files under `target/slimtest/`; change their source or the
  generator instead.
- Do not manually update release-managed version or changelog files for an
  ordinary feature, fix, documentation, refactor, or test change. See
  `agent/rules/release.md`.
- Keep slimtest a thin layer over dbt. Prefer emitting standard dbt inputs and
  interpreting standard dbt artifacts over reimplementing dbt behavior.
- Add or update tests for observable behavior changes.
- Before handing off changes, run the checks required by
  `agent/rules/quality.md` and report any check that could not run.

## Source-of-truth order

When project documents disagree, use this order and fix the stale document as
part of the task when it is in scope:

1. Executable behavior and tests in `src/` and `tests/`.
2. The runnable contract in `examples/sample_dbt_project/`.
3. Current user documentation in `README.md`.
4. Knowledge documents under `agent/knowledges/`.
5. Historical context in `design.md`.
