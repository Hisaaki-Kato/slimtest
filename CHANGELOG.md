# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1](https://github.com/Hisaaki-Kato/slimtest/compare/v0.1.0...v0.1.1) (2026-07-17)


### Bug Fixes

* tolerate unrelated and duplicate-key model ymls during compile ([#4](https://github.com/Hisaaki-Kato/slimtest/issues/4)) ([865938c](https://github.com/Hisaaki-Kato/slimtest/commit/865938c24ff33da60cbd6b59ca352db4d265be59))

## [Unreleased]

## [0.1.0] - 2026-07-07

Initial public release.

### Added

- CLI: `slimtest compile` and `slimtest unittest` with `--project-dir` and `--select` options.
- Factory + trait + override DSL under `tests/slimtest_factories/*.yml`, resolved via deep-merge (`base` → `trait` → `override`).
- Test blocks under `models[*].meta.slimtest.unit_tests` in dbt model YAML.
- `given:` accepts the more compact `{upstream: [rows]}` dict form (instead of dbt's list-of-pairs).
- `model:` field inferred from the enclosing `models[*].name`.
- Automatic `ref()` vs `source()` disambiguation via `target/manifest.json`.
- Upstream auto-fill: any upstream that a model depends on but the test omits is stitched in from the same-named factory's `base` row (opt-out via `slimtest.yml`).
- `parametrize:` block to expand one test into N via `$column` substitution, with case-id naming.
- `scenarios:` block under `meta.slimtest` for shared `given:` bundles referenced by `scenario: <name>`.
- Partial `expect:` — only list the columns the test asserts about (dbt ignores unmentioned columns).
- Source map: failures from `dbt test` are mapped back to `<model.yml>:<line>` in the CLI output.
- Test name prefix `slimtest__<model>__<name>` guarantees no collision with hand-written dbt `unit_tests`.
- `--select` accepts a model name, the user-written test name, the prefixed test name, `test_type:unit`, or a comma-separated union.
- `--verbose` / `-v` flag: INFO-level notices (e.g. auto-injected upstream rows) are hidden by default and printed under verbose.
- `slimtest.yml` project config with `factories_path`, `generated_yml_path`, `auto_fill_upstreams`.
- Works with any dbt adapter; validated end-to-end against dbt-duckdb.

### Documentation

- Project README with why / install / quick start / concepts / coverage / commands / development.
- Runnable end-to-end example at `examples/sample_dbt_project/` (DuckDB, 5 test definitions → 8 dbt unit tests).
- MIT `LICENSE`.
- Non-affiliation disclaimer and dbt trademark notice in README.

[Unreleased]: https://github.com/Hisaaki-Kato/slimtest/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Hisaaki-Kato/slimtest/releases/tag/v0.1.0
