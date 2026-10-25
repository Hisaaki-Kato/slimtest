# Compatibility rules

## Scope

These rules apply to the public DSL, `slimtest.yml`, CLI options and output,
generated dbt YAML, selectors, factory behavior, source mapping, and dbt
integration.

## Preserve the dbt boundary

- Keep slimtest a preprocessor and orchestrator over standard dbt unit tests.
- Prefer manifest and run-result data produced by dbt over reimplementing dbt
  parsing or execution semantics.
- Pass dbt-owned values such as macro, var, and environment overrides through
  without interpreting their contents.
- Preserve resource identity: model, source, package, and version distinctions
  must not be collapsed when they affect generated input expressions.

## Preserve authoring semantics

Unless a task explicitly introduces a breaking change:

- keep factory resolution as `base -> trait -> override` with deep merge;
- keep scenario `given` merging test-wins per upstream key;
- keep override precedence as `project < model < scenario < test`, merged by
  key within each dbt override section;
- keep the enclosing dbt model as the inferred target;
- keep literal rows valid alongside factory rows;
- keep generated names isolated with `slimtest__<model>__<name>`;
- keep hand-written top-level dbt unit tests untouched;
- keep `given.this` reserved for incremental current-state input.

## Fail explicitly

- Reject unknown user-facing schema fields instead of silently discarding
  them.
- Reject ambiguous upstream identities and instruct the user to qualify them.
- Reject unsupported selector syntax instead of approximating it.
- Treat missing, duplicate, unexpected, and unknown dbt test results as
  integrity errors.
- Do not let stale manifest or run-results artifacts turn a failed invocation
  into an apparent success.

## Observable changes

For a public behavior change:

1. Identify whether existing YAML, commands, or generated output changes.
2. Preserve the old behavior when practical, or make the breaking nature
   explicit.
3. Add focused unit tests at the layer that owns the behavior.
4. Add or update integration coverage when the change crosses parsing,
   expansion, artifact generation, or dbt execution boundaries.
5. Update the README and runnable sample when users need to understand or adopt
   the behavior.
6. Use the appropriate Conventional Commit category from
   `agent/rules/release.md`.

## Source-location invariant

Generated names and concrete dbt IDs may differ, especially for parametrized
or versioned tests. Any naming or manifest change must preserve mapping back to
the original user-written test and source line.
