"""Orchestrate the `lighttest unittest` end-to-end flow.

  1. `dbt parse` to refresh `target/manifest.json`.
  2. `compile_project()` using the fresh manifest.
  3. `dbt test --select <generated test names>`.
  4. Load `target/run_results.json` and enrich each failure with the
     source location recorded by the compile step.

The CLI layer turns the result into output; everything else here is
plain data so the orchestrator can be unit-tested with mocked dbt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .compile import CompileResult, compile_project
from .dbt_runner import DbtResult, dbt_parse, dbt_test
from .factory import LightTestError
from .manifest import Manifest, ManifestNotFoundError
from .result_parser import (
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
    """Everything one `lighttest unittest` invocation produces."""

    compile: CompileResult
    parse_result: DbtResult
    test_result: DbtResult
    outcomes: list[EnrichedOutcome]
    summary: TestSummary

    @property
    def ok(self) -> bool:
        return self.parse_result.ok and self.test_result.ok and self.summary.ok


def unittest_project(
    project_root: Path, *, select: str | None = None
) -> UnittestResult:
    """End-to-end `lighttest unittest` orchestration.

    `dbt parse` is best-effort: a non-zero exit is reported on the
    result but does not abort the run. `select` is forwarded to
    `compile_project` (see `selector.py`).
    """
    project_root = project_root.resolve()

    parse_result = dbt_parse(project_root)
    manifest = _try_manifest(project_root)
    compile_result = compile_project(project_root, manifest=manifest, select=select)
    test_result = dbt_test(project_root, compile_result.test_names)

    outcomes = _enrich_outcomes(project_root, compile_result)
    summary = summarize([e.outcome for e in outcomes])

    return UnittestResult(
        compile=compile_result,
        parse_result=parse_result,
        test_result=test_result,
        outcomes=outcomes,
        summary=summary,
    )


def _try_manifest(project_root: Path) -> Manifest | None:
    try:
        return Manifest.load(project_root)
    except ManifestNotFoundError:
        return None
    except LightTestError:
        # Malformed manifest -- fall back to no-manifest mode rather than
        # blowing up the whole run. The compile step warns the user via
        # bare-ref output and dbt will surface the real error.
        return None


def _enrich_outcomes(
    project_root: Path, compile_result: CompileResult
) -> list[EnrichedOutcome]:
    """Pair each run_results.json entry with its source-map record.

    Returns `[]` if the run_results file is missing (e.g. `dbt test` was
    a no-op because no tests were compiled).
    """
    if not compile_result.test_names:
        return []

    try:
        raw = load_run_results(project_root)
    except LightTestError:
        return []

    smap = compile_result.source_map
    enriched: list[EnrichedOutcome] = []
    for outcome in raw:
        entry = smap.get(outcome.name)
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


__all__ = [
    "EnrichedOutcome",
    "UnittestResult",
    "unittest_project",
]
