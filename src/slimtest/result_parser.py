"""Read dbt's `target/run_results.json` after `dbt test`.

We use the structured JSON output rather than scraping stdout: dbt's
text format is colourful and somewhat unstable across versions; the
JSON shape has been steady since dbt 1.x.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from .factory import SlimTestError

RUN_RESULTS_RELATIVE_PATH = Path("target") / "run_results.json"

# dbt result statuses we care about. There are more, but for unit tests
# `pass`/`fail`/`error` (+ skip) are the relevant outcomes.
TestStatus = Literal["pass", "fail", "error", "skipped", "unknown"]


@dataclass(frozen=True)
class TestOutcome:
    """One row of the `dbt test` result table."""

    unique_id: str  # e.g. "unit_test.proj.model.test_name"
    name: str  # the test name dbt reports; what we generated
    status: TestStatus
    execution_time: float
    message: str | None = None
    raw_status: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "pass"


class InvalidRunResultsError(SlimTestError):
    """`run_results.json` is missing or malformed."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid run_results {path}: {detail}")
        self.path = path


def load_run_results(project_root: Path) -> list[TestOutcome]:
    """Read `<project_root>/target/run_results.json` and project test results."""
    path = project_root / RUN_RESULTS_RELATIVE_PATH
    if not path.exists():
        raise InvalidRunResultsError(path, "file does not exist")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data: Any = json.load(fh)
    except Exception as exc:  # noqa: BLE001 -- json raises broadly
        raise InvalidRunResultsError(path, str(exc)) from exc
    if not isinstance(data, dict):
        raise InvalidRunResultsError(
            path, f"expected JSON object at top level, got {type(data).__name__}"
        )

    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        raise InvalidRunResultsError(path, "`results` key is missing or not a list")

    return [outcome for entry in raw_results if (outcome := _to_outcome(entry))]


def _to_outcome(entry: Any) -> TestOutcome | None:
    """Best-effort projection of one results entry. Skips non-test rows."""
    if not isinstance(entry, dict):
        return None
    unique_id = entry.get("unique_id")
    if not isinstance(unique_id, str) or not unique_id.startswith("unit_test."):
        # We only care about unit tests; ignore models, data tests, etc.
        return None
    status_value = entry.get("status")
    if not isinstance(status_value, str):
        return None
    status: TestStatus
    raw_status: str | None = None
    if status_value in ("pass", "fail", "error", "skipped"):
        status = cast(TestStatus, status_value)
    else:
        status = "unknown"
        raw_status = status_value
    name = unique_id.rsplit(".", 1)[-1]
    return TestOutcome(
        unique_id=unique_id,
        name=name,
        status=status,
        execution_time=float(entry.get("execution_time") or 0.0),
        message=entry.get("message") if isinstance(entry.get("message"), str) else None,
        raw_status=raw_status,
    )


@dataclass(frozen=True)
class TestSummary:
    """Aggregated outcome counts across a `dbt test` run."""

    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    unknown: int = 0

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.errored == 0 and self.unknown == 0


def summarize(outcomes: list[TestOutcome]) -> TestSummary:
    passed = sum(1 for o in outcomes if o.status == "pass")
    failed = sum(1 for o in outcomes if o.status == "fail")
    errored = sum(1 for o in outcomes if o.status == "error")
    skipped = sum(1 for o in outcomes if o.status == "skipped")
    unknown = sum(1 for o in outcomes if o.status == "unknown")
    return TestSummary(
        total=len(outcomes),
        passed=passed,
        failed=failed,
        errored=errored,
        skipped=skipped,
        unknown=unknown,
    )


__all__ = [
    "RUN_RESULTS_RELATIVE_PATH",
    "InvalidRunResultsError",
    "TestOutcome",
    "TestStatus",
    "TestSummary",
    "load_run_results",
    "summarize",
]
