"""Tests for `lighttest.runner.unittest_project`.

dbt is fully mocked out -- we patch `dbt_parse` and `dbt_test` in the
`lighttest.runner` namespace and synthesize a `run_results.json` to
exercise the parsing / source-map enrichment path.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from lighttest.dbt_runner import DbtResult
from lighttest.runner import unittest_project

# -- helpers --------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


def _make_minimal_project(tmp_path: Path, *, with_test: bool = True) -> Path:
    (tmp_path / "models").mkdir()
    if with_test:
        _write(
            tmp_path / "models" / "m.yml",
            """
            models:
              - name: m
                meta:
                  lighttest:
                    unit_tests:
                      - name: t
                        given:
                          users:
                            - {x: 1}
                        expect: []
            """,
        )
    return tmp_path


def _write_run_results(project_root: Path, results: list[dict]) -> None:
    target = project_root / "target"
    target.mkdir(parents=True, exist_ok=True)
    (target / "run_results.json").write_text(
        json.dumps({"results": results}), encoding="utf-8"
    )


_DBT_OK = DbtResult(0, "", "")


def _fake_dbt(monkeypatch, *, parse=None, test=None):
    parse = parse if parse is not None else _DBT_OK
    test = test if test is not None else _DBT_OK
    monkeypatch.setattr("lighttest.runner.dbt_parse", lambda _root: parse)
    monkeypatch.setattr("lighttest.runner.dbt_test", lambda _root, _names: test)


# -- happy path -----------------------------------------------------


class TestUnittestProject:
    def test_zero_tests_returns_ok(self, monkeypatch, tmp_path):
        _make_minimal_project(tmp_path, with_test=False)
        _fake_dbt(monkeypatch)
        result = unittest_project(tmp_path)
        assert result.compile.test_count == 0
        assert result.ok
        assert result.outcomes == []

    def test_single_passing_test(self, monkeypatch, tmp_path):
        project = _make_minimal_project(tmp_path)
        _fake_dbt(monkeypatch)
        _write_run_results(
            project,
            [
                {
                    "unique_id": "unit_test.proj.m.lighttest__m__t",
                    "status": "pass",
                    "execution_time": 0.1,
                }
            ],
        )
        result = unittest_project(project)
        assert result.ok
        assert result.summary.total == 1
        assert result.summary.passed == 1
        # The single outcome was enriched with source info.
        assert result.outcomes[0].source_file == Path("models/m.yml")
        assert result.outcomes[0].original_name == "t"

    def test_failing_test_marks_run_not_ok(self, monkeypatch, tmp_path):
        project = _make_minimal_project(tmp_path)
        _fake_dbt(monkeypatch, test=DbtResult(1, "", ""))
        _write_run_results(
            project,
            [
                {
                    "unique_id": "unit_test.proj.m.lighttest__m__t",
                    "status": "fail",
                    "execution_time": 0.1,
                    "message": "row count mismatch",
                }
            ],
        )
        result = unittest_project(project)
        assert not result.ok
        assert result.summary.failed == 1
        assert result.outcomes[0].outcome.message == "row count mismatch"

    def test_dbt_parse_failure_is_recorded_but_run_continues(
        self, monkeypatch, tmp_path
    ):
        project = _make_minimal_project(tmp_path)
        _fake_dbt(monkeypatch, parse=DbtResult(2, "", "parse err"))
        _write_run_results(
            project,
            [
                {
                    "unique_id": "unit_test.proj.m.lighttest__m__t",
                    "status": "pass",
                    "execution_time": 0.1,
                }
            ],
        )
        result = unittest_project(project)
        assert result.parse_result.exit_code == 2
        # Run still produced an outcome.
        assert result.summary.passed == 1
        # But overall .ok reflects the parse failure.
        assert not result.ok

    def test_run_results_missing_when_dbt_test_failed_hard(self, monkeypatch, tmp_path):
        # dbt test bails before writing run_results.json -- we don't crash,
        # we just report zero outcomes and surface stderr at the CLI.
        _make_minimal_project(tmp_path)
        _fake_dbt(monkeypatch, test=DbtResult(2, "", "dbt blew up"))
        result = unittest_project(tmp_path)
        assert not result.ok
        assert result.outcomes == []
        assert result.test_result.stderr == "dbt blew up"

    def test_outcome_unknown_to_source_map_keeps_none_location(
        self, monkeypatch, tmp_path
    ):
        project = _make_minimal_project(tmp_path)
        _fake_dbt(monkeypatch)
        _write_run_results(
            project,
            [
                {
                    "unique_id": "unit_test.proj.other.something_unrelated",
                    "status": "pass",
                    "execution_time": 0.1,
                }
            ],
        )
        result = unittest_project(project)
        assert len(result.outcomes) == 1
        assert result.outcomes[0].source_file is None
        assert result.outcomes[0].original_name is None
