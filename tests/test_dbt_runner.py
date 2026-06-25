"""Tests for `lighttest.dbt_runner`.

We don't want these to fork actual `dbt` processes during pytest, so
the heavy lifting is mocked via monkeypatch on `subprocess.run` and
`shutil.which`. A separate live smoke test (run manually against the
sample project) checks the real subprocess path.
"""

from __future__ import annotations

import subprocess  # noqa: F401 -- imported for type info / monkeypatching
from typing import Any

import pytest

from lighttest.dbt_runner import (
    DbtNotInstalledError,
    DbtResult,
    dbt_parse,
    dbt_test,
    run_dbt,
)

# -- helpers --------------------------------------------------------


class _RecordingRun:
    """Capture the last call to subprocess.run and synthesize a result."""

    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[dict[str, Any]] = []

    def __call__(self, args, **kwargs):  # noqa: ANN001 -- mirrors subprocess.run
        self.calls.append({"args": args, **kwargs})

        class _Completed:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err

        return _Completed(self.returncode, self.stdout, self.stderr)


@pytest.fixture
def _have_dbt(monkeypatch):
    """Pretend `dbt` is on PATH."""
    monkeypatch.setattr(
        "lighttest.dbt_runner.shutil.which",
        lambda name: "/fake/dbt" if name == "dbt" else None,
    )


@pytest.fixture
def _no_dbt(monkeypatch):
    monkeypatch.setattr(
        "lighttest.dbt_runner.shutil.which",
        lambda _name: None,
    )


# -- DbtResult -----------------------------------------------------


class TestDbtResult:
    def test_ok_when_exit_code_zero(self):
        assert DbtResult(0, "", "").ok is True

    def test_not_ok_when_exit_code_nonzero(self):
        assert DbtResult(1, "", "").ok is False


# -- run_dbt -------------------------------------------------------


@pytest.mark.usefixtures("_have_dbt")
class TestRunDbt:
    def test_invokes_subprocess_with_dbt_prefix(self, monkeypatch, tmp_path):
        recorder = _RecordingRun(returncode=0, stdout="ok", stderr="")
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        result = run_dbt(["test", "--select", "x"], tmp_path)
        assert result == DbtResult(0, "ok", "")
        assert recorder.calls[0]["args"] == ["dbt", "test", "--select", "x"]
        assert recorder.calls[0]["cwd"] == str(tmp_path)
        assert recorder.calls[0]["capture_output"] is True
        assert recorder.calls[0]["text"] is True

    def test_sets_profiles_dir_when_profiles_yml_exists(self, monkeypatch, tmp_path):
        (tmp_path / "profiles.yml").write_text("default: {}\n", encoding="utf-8")
        recorder = _RecordingRun()
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        run_dbt(["parse"], tmp_path, env={})  # explicit empty env
        env = recorder.calls[0]["env"]
        assert env["DBT_PROFILES_DIR"] == str(tmp_path)

    def test_does_not_override_existing_profiles_dir(self, monkeypatch, tmp_path):
        (tmp_path / "profiles.yml").write_text("default: {}\n", encoding="utf-8")
        recorder = _RecordingRun()
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        run_dbt(["parse"], tmp_path, env={"DBT_PROFILES_DIR": "/elsewhere"})
        env = recorder.calls[0]["env"]
        assert env["DBT_PROFILES_DIR"] == "/elsewhere"

    def test_does_not_set_profiles_dir_when_no_profiles_yml(
        self, monkeypatch, tmp_path
    ):
        recorder = _RecordingRun()
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        run_dbt(["parse"], tmp_path, env={})
        env = recorder.calls[0]["env"]
        assert "DBT_PROFILES_DIR" not in env

    def test_propagates_nonzero_exit_code(self, monkeypatch, tmp_path):
        recorder = _RecordingRun(returncode=2, stdout="boom", stderr="err")
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        result = run_dbt(["test"], tmp_path)
        assert result == DbtResult(2, "boom", "err")


@pytest.mark.usefixtures("_no_dbt")
def test_run_dbt_raises_when_dbt_missing(tmp_path):
    with pytest.raises(DbtNotInstalledError):
        run_dbt(["parse"], tmp_path)


# -- dbt_parse / dbt_test convenience wrappers --------------------


@pytest.mark.usefixtures("_have_dbt")
class TestDbtParse:
    def test_passes_parse_arg(self, monkeypatch, tmp_path):
        recorder = _RecordingRun()
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        dbt_parse(tmp_path)
        assert recorder.calls[0]["args"] == ["dbt", "parse"]


@pytest.mark.usefixtures("_have_dbt")
class TestDbtTest:
    def test_runs_test_with_selectors(self, monkeypatch, tmp_path):
        recorder = _RecordingRun()
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        dbt_test(tmp_path, ["a", "b"])
        # Names are joined into one --select token, space separated.
        assert recorder.calls[0]["args"] == ["dbt", "test", "--select", "a b"]

    def test_empty_test_list_short_circuits(self, monkeypatch, tmp_path):
        recorder = _RecordingRun()
        monkeypatch.setattr("lighttest.dbt_runner.subprocess.run", recorder)
        result = dbt_test(tmp_path, [])
        assert result == DbtResult(0, "", "")
        # We never spawned subprocess.
        assert recorder.calls == []
