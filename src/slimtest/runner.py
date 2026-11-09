"""Orchestrate the `slimtest unittest` end-to-end flow.

  1. `dbt parse` to refresh `target/manifest.json`.
  2. `compile_project()` using the fresh manifest.
  3. `dbt test --select <generated test names>`.
  4. Load `target/run_results.json` and enrich each failure with the
     source location recorded by the compile step.

The CLI layer turns the result into output; everything else here is
plain data so the orchestrator can be unit-tested with mocked dbt.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path

from .artifacts import temporarily_hide_generated_yml
from .compile import CompileResult, compile_project
from .dbt_runner import DbtInvocationError, DbtResult, dbt_parse, dbt_test
from .factory import SlimTestError
from .manifest import MANIFEST_RELATIVE_PATH, Manifest, ManifestNotFoundError
from .result_parser import (
    RUN_RESULTS_RELATIVE_PATH,
    TestOutcome,
    TestSummary,
    load_run_results,
    summarize,
)


@dataclass(frozen=True)
class EnrichedOutcome:
    """A `TestOutcome` augmented with where its source lives."""

    outcome: TestOutcome
    source_file: Path | None
    source_line: int | None
    original_name: str | None


@dataclass(frozen=True)
class UnittestResult:
    """Everything one `slimtest unittest` invocation produces."""

    compile: CompileResult
    parse_result: DbtResult
    test_result: DbtResult
    outcomes: list[EnrichedOutcome]
    summary: TestSummary
    integrity_errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            self.parse_result.ok
            and self.test_result.ok
            and self.summary.ok
            and not self.integrity_errors
        )


def unittest_project(
    project_root: Path,
    *,
    select: str | None = None,
    target: str | None = None,
    profile: str | None = None,
    profiles_dir: Path | None = None,
) -> UnittestResult:
    """End-to-end `slimtest unittest` orchestration.

    A non-zero `dbt parse` aborts before compilation so stale manifest data
    cannot drive generated inputs. `select` is forwarded to `compile_project`
    (see `selector.py`). Profile and target options are forwarded consistently
    to both dbt invocations.
    """
    project_root = project_root.resolve()

    with temporarily_hide_generated_yml(project_root) as hidden:
        _discard_artifact(project_root / MANIFEST_RELATIVE_PATH)
        parse_result = dbt_parse(
            project_root,
            target=target,
            profile=profile,
            profiles_dir=profiles_dir,
        )
        if not parse_result.ok:
            raise DbtInvocationError("parse", parse_result)
        manifest = _try_manifest(project_root)
        compile_result = compile_project(project_root, manifest=manifest, select=select)
        hidden.commit()

        # A result is trustworthy only if dbt created both JSON artifacts
        # during this invocation. Removing the prior files also prevents a
        # successful old run from masking a no-op or an early dbt failure.
        if compile_result.test_names:
            _discard_artifact(project_root / MANIFEST_RELATIVE_PATH)
            _discard_artifact(project_root / RUN_RESULTS_RELATIVE_PATH)
        test_result = dbt_test(
            project_root,
            compile_result.test_names,
            target=target,
            profile=profile,
            profiles_dir=profiles_dir,
        )

        raw_outcomes, logical_names, integrity_errors = _validated_outcomes(
            project_root, compile_result
        )
        outcomes = _enrich_outcomes(raw_outcomes, logical_names, compile_result)
        summary = summarize([e.outcome for e in outcomes])

    return UnittestResult(
        compile=compile_result,
        parse_result=parse_result,
        test_result=test_result,
        outcomes=outcomes,
        summary=summary,
        integrity_errors=tuple(integrity_errors),
    )


def _try_manifest(project_root: Path) -> Manifest | None:
    try:
        return Manifest.load(project_root)
    except ManifestNotFoundError:
        return None
    except SlimTestError:
        # Malformed manifest -- fall back to no-manifest mode rather than
        # blowing up the whole run. The compile step warns the user via
        # bare-ref output and dbt will surface the real error.
        return None


def _validated_outcomes(
    project_root: Path, compile_result: CompileResult
) -> tuple[list[TestOutcome], dict[str, str], list[str]]:
    """Load fresh artifacts and reconcile dbt's actual IDs with this run."""
    if not compile_result.test_names:
        return [], {}, []

    errors: list[str] = []
    try:
        manifest = Manifest.load(project_root)
    except SlimTestError as exc:
        errors.append(str(exc))
        manifest = None

    logical_names = (
        manifest.selected_unit_tests(
            compile_result.test_names,
            {
                name: str(compile_result.source_map[name]["model"])
                for name in compile_result.test_names
                if name in compile_result.source_map
            },
        )
        if manifest is not None
        else {}
    )
    if manifest is not None and not logical_names:
        errors.append(
            "fresh dbt manifest contains none of the selected slimtest unit tests"
        )
    elif manifest is not None:
        missing_logical_names = sorted(
            set(compile_result.test_names) - set(logical_names.values())
        )
        if missing_logical_names:
            errors.append(
                "fresh dbt manifest is missing selected slimtest unit tests: "
                f"{missing_logical_names}"
            )

    try:
        raw = load_run_results(project_root)
    except SlimTestError as exc:
        errors.append(str(exc))
        return [], logical_names, errors

    actual_by_id: dict[str, TestOutcome] = {}
    duplicate_ids: set[str] = set()
    for outcome in raw:
        if outcome.unique_id in actual_by_id:
            duplicate_ids.add(outcome.unique_id)
        actual_by_id[outcome.unique_id] = outcome
    if duplicate_ids:
        errors.append(
            f"dbt produced duplicate unit-test results: {sorted(duplicate_ids)}"
        )
    expected_ids = set(logical_names)
    actual_ids = set(actual_by_id)
    missing = sorted(expected_ids - actual_ids)
    unexpected = sorted(actual_ids - expected_ids)
    if missing:
        errors.append(f"dbt produced no result for expected unit tests: {missing}")
    if unexpected:
        errors.append(f"dbt produced unexpected unit-test results: {unexpected}")

    selected = [
        actual_by_id[test_id] for test_id in logical_names if test_id in actual_by_id
    ]
    unknown = [
        f"{outcome.unique_id}={outcome.raw_status!r}"
        for outcome in selected
        if outcome.status == "unknown"
    ]
    if unknown:
        errors.append(f"dbt produced unknown unit-test statuses: {unknown}")
    return selected, logical_names, errors


def _enrich_outcomes(
    raw: list[TestOutcome],
    logical_names: dict[str, str],
    compile_result: CompileResult,
) -> list[EnrichedOutcome]:
    """Pair each run_results.json entry with its source-map record.

    Version-expanded dbt IDs are mapped through the manifest's unit-test name
    before looking up the source map.
    """
    smap = compile_result.source_map
    enriched: list[EnrichedOutcome] = []
    for outcome in raw:
        logical_name = logical_names.get(outcome.unique_id, outcome.name)
        outcome = replace(outcome, name=logical_name)
        entry = smap.get(logical_name)
        if entry is None:
            enriched.append(
                EnrichedOutcome(
                    outcome=outcome,
                    source_file=None,
                    source_line=None,
                    original_name=None,
                )
            )
            continue
        enriched.append(
            EnrichedOutcome(
                outcome=outcome,
                source_file=Path(entry["source_file"]),
                source_line=int(entry["source_line"]),
                original_name=entry.get("original_name"),
            )
        )
    return enriched


def _discard_artifact(path: Path) -> None:
    """Remove one dbt-generated JSON artifact before invoking dbt."""
    with suppress(FileNotFoundError):
        path.unlink()


__all__ = [
    "EnrichedOutcome",
    "UnittestResult",
    "unittest_project",
]
