"""Subprocess wrapper for invoking dbt.

MVP design (matches design.md §11.1): we shell out to `dbt`. The next
optimisation step (v0.3+) would be the in-process `dbtRunner` API; the
interface here is stable enough that that swap stays local.

If the project has a sibling `profiles.yml`, we set `DBT_PROFILES_DIR`
so the project is runnable straight from a fresh clone -- mirroring the
manual `DBT_PROFILES_DIR=. dbt seed` pattern used in the sample.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .factory import LightTestError

PROFILES_FILENAME = "profiles.yml"


@dataclass(frozen=True)
class DbtResult:
    """Outcome of a single dbt invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class DbtNotInstalledError(LightTestError):
    """`dbt` is not on PATH."""

    def __init__(self) -> None:
        super().__init__(
            "`dbt` was not found on PATH. Install dbt-core and the appropriate "
            "adapter (e.g. `pip install dbt-duckdb`) before running lighttest unittest."
        )


def _ensure_dbt() -> None:
    if shutil.which("dbt") is None:
        raise DbtNotInstalledError


def _dbt_env(
    project_root: Path, base: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Build the env dict for a dbt subprocess.

    If `<project_root>/profiles.yml` exists and the caller hasn't already
    set `DBT_PROFILES_DIR`, point dbt at the project root.
    """
    env: dict[str, str] = dict(base if base is not None else os.environ)
    if "DBT_PROFILES_DIR" not in env and (project_root / PROFILES_FILENAME).exists():
        env["DBT_PROFILES_DIR"] = str(project_root)
    return env


def run_dbt(
    args: list[str],
    project_root: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> DbtResult:
    """Run `dbt <args>` from `project_root` and capture output.

    `env` overrides the inherited environment entirely (after the
    profiles-dir auto-injection step), which makes the function easy to
    test with monkeypatch.setenv.
    """
    _ensure_dbt()
    proc_env = _dbt_env(project_root, env)
    # noqa S603: args are constructed by lighttest itself, not by the user.
    completed = subprocess.run(  # noqa: S603
        ["dbt", *args],
        cwd=str(project_root),
        check=False,
        capture_output=True,
        text=True,
        env=proc_env,
    )
    return DbtResult(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def dbt_parse(project_root: Path) -> DbtResult:
    """Run `dbt parse` to rebuild `target/manifest.json`."""
    return run_dbt(["parse"], project_root)


def dbt_test(project_root: Path, test_names: list[str]) -> DbtResult:
    """Run `dbt test --select <names>`.

    An empty `test_names` list returns a synthetic success so callers
    don't have to special-case the "zero tests compiled" path.
    """
    if not test_names:
        return DbtResult(exit_code=0, stdout="", stderr="")
    return run_dbt(
        ["test", "--select", " ".join(test_names)],
        project_root,
    )


__all__ = [
    "PROFILES_FILENAME",
    "DbtNotInstalledError",
    "DbtResult",
    "dbt_parse",
    "dbt_test",
    "run_dbt",
]
