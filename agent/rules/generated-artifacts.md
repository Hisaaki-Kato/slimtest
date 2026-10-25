# Generated artifact rules

## Scope

These rules apply to `target/slimtest/`, artifact publication, generated YAML,
source maps, and code that hides or replaces artifacts around dbt invocations.

## Source and ownership

- Never hand-edit generated YAML, `source_map.json`, or the artifact inventory.
- Change user-authored YAML, generator code, or tests instead.
- Every generated YAML file must retain the slimtest generated header.
- Only files verifiably owned by slimtest may be replaced or removed.
- Refuse to overwrite a conflicting unowned file, including a symlink.

## Publication behavior

- Render and validate the complete desired artifact set before replacing the
  previously published set.
- Keep publication rollback-capable. A failure must restore the previous
  complete set or retain an explicit recovery directory and report it.
- Remove stale slimtest-owned generated files when a successful compile no
  longer produces them.
- Preserve unrelated files in the configured generated directory.
- Serialize cooperating publishers for the same output directory.

## Parse and compile interaction

- Hide only slimtest-owned generated YAML before the initial `dbt parse`.
- Restore the previous generated set if parse or compile fails before a new set
  has been committed.
- Do not allow stale generated YAML for a removed or renamed model to influence
  the fresh dbt manifest.

## Selection invariant

`--select` chooses which logical tests are run or reported. It must not publish
a partial artifact universe that makes a later dbt parse depend on the most
recent selector.

## Required tests

Changes in this area need coverage for the relevant success path and failure
or rollback path. Include ownership conflicts and stale-file cleanup when the
change can affect them.
