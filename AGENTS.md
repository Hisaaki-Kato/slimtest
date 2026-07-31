# Repository instructions

These instructions apply to the entire repository.

## Release management

- Releases are managed by release-please through
  `.github/workflows/release.yml`, `release-please-config.json`, and
  `.release-please-manifest.json`.
- For ordinary feature, fix, documentation, refactor, and test changes, do not
  manually edit:
  - the project version in `pyproject.toml`;
  - `.release-please-manifest.json`;
  - release entries in `CHANGELOG.md`.
- Let the release-please release PR update the version, manifest, and changelog.
  Only edit those files when the task explicitly concerns release tooling,
  release metadata, or a release-please-generated release PR.
- `uv` may update the editable `slimtest` package version recorded in
  `uv.lock`. Do not retain a version-only `uv.lock` change caused incidentally
  by local commands unless the task explicitly requires it.

## Pull request and commit convention

- This repository uses squash merge. The pull request title becomes the commit
  subject on `main` and is consumed by release-please.
- Pull request titles must follow Conventional Commits. Examples:
  - `feat: support dbt unit test overrides`
  - `fix: preserve overrides during parametrization`
  - `docs: explain override precedence`
  - `feat!: remove a deprecated input format`
- Use `feat:` for user-facing functionality and `fix:` for bug fixes. With the
  current pre-1.0 release-please settings, `feat:` advances the minor version
  (for example, `0.1.x` to `0.2.0`).
- Do not use a release-style title such as `chore(main): release ...` for a
  normal pull request; release-please creates that release PR itself.

## Quality gate

Before handing off code changes, run the same checks as CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
```
