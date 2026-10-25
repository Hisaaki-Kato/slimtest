# Release and pull-request rules

## Scope

These rules apply to release metadata, commits, pull requests, and any command
that may rewrite the lockfile or project version.

## Release ownership

Releases are managed by release-please through:

- `.github/workflows/release.yml`;
- `release-please-config.json`;
- `.release-please-manifest.json`.

For an ordinary feature, fix, documentation, refactor, or test change, do not
manually edit:

- the project version in `pyproject.toml`;
- `.release-please-manifest.json`;
- release entries in `CHANGELOG.md`.

Only edit those files when the task explicitly concerns release tooling,
release metadata, or a release-please-generated release pull request.

`uv` may incidentally update the editable `slimtest` package version recorded
in `uv.lock`. Do not retain a version-only lockfile change unless the task
requires it.

## Pull-request titles

The repository uses squash merge. The pull-request title becomes the commit
subject on `main` and is consumed by release-please.

Titles must follow Conventional Commits. Use:

- `feat:` for user-facing functionality;
- `fix:` for bug fixes;
- `docs:` for documentation-only changes;
- `refactor:` for internal restructuring without a behavior change;
- `test:` for test-only changes;
- `feat!:` or another breaking marker for an intentional breaking change.

Examples:

- `feat: support dbt unit test overrides`
- `fix: preserve overrides during parametrization`
- `docs: explain override precedence`
- `feat!: remove a deprecated input format`

Do not use a release-style title such as `chore(main): release ...` for a
normal pull request. release-please creates the release pull request itself.

## Verification

Before proposing a title, classify the observable effect of the change. When
a change affects public behavior, apply `agent/rules/compatibility.md` as well.
