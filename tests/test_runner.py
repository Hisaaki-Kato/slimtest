"""Tests for `slimtest.runner.unittest_project`.

dbt is fully mocked out -- we patch `dbt_parse` and `dbt_test` in the
`slimtest.runner` namespace and synthesize a `run_results.json` to
exercise the parsing / source-map enrichment path.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from slimtest.dbt_runner import DbtResult
from slimtest.runner import unittest_project

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
                  slimtest:
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
    unit_tests = {
        entry["unique_id"]: {
            "unique_id": entry["unique_id"],
            "name": entry.get("name", entry["unique_id"].rsplit(".", 1)[-1]),
            "depends_on": {"nodes": ["model.proj.m"]},
        }
        for entry in results
        if entry.get("unique_id", "").startswith("unit_test.")
    }
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "nodes": {"model.proj.m": {"resource_type": "model", "name": "m"}},
                "sources": {},
                "unit_tests": unit_tests,
            }
        ),
        encoding="utf-8",
    )


_DBT_OK = DbtResult(0, "", "")


def _fake_dbt(monkeypatch, *, parse=None, test=None, results=None):
    parse = parse if parse is not None else _DBT_OK
    test = test if test is not None else _DBT_OK
    monkeypatch.setattr("slimtest.runner.dbt_parse", lambda _root, **_kwargs: parse)

    def fake_test(root, _names, **_kwargs):
        if results is not None:
            _write_run_results(root, results)
        return test

    monkeypatch.setattr("slimtest.runner.dbt_test", fake_test)


# -- happy path -----------------------------------------------------


class TestUnittestProject:
    def test_forwards_profile_and_target_options(self, monkeypatch, tmp_path):
        _make_minimal_project(tmp_path, with_test=False)
        calls: list[tuple[Any, ...]] = []

        def fake_parse(root, **kwargs):
            calls.append(("parse", root, kwargs))
            return _DBT_OK

        def fake_test(root, names, **kwargs):
            calls.append(("test", root, names, kwargs))
            return _DBT_OK

        monkeypatch.setattr("slimtest.runner.dbt_parse", fake_parse)
        monkeypatch.setattr("slimtest.runner.dbt_test", fake_test)
        profiles_dir = tmp_path / "dbt-profiles"

        unittest_project(
            tmp_path,
            target="ci",
            profile="analytics",
            profiles_dir=profiles_dir,
        )

        expected = {
            "target": "ci",
            "profile": "analytics",
            "profiles_dir": profiles_dir,
        }
        assert calls[0] == ("parse", tmp_path.resolve(), expected)
        assert calls[1] == ("test", tmp_path.resolve(), [], expected)

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
                    "unique_id": "unit_test.proj.m.slimtest__m__t",
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
                    "unique_id": "unit_test.proj.m.slimtest__m__t",
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
                    "unique_id": "unit_test.proj.m.slimtest__m__t",
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

    def test_versioned_dbt_ids_share_logical_source_mapping(
        self, monkeypatch, tmp_path
    ):
        project = _make_minimal_project(tmp_path)
        results = [
            {
                "unique_id": f"unit_test.proj.m.slimtest__m__t_v{version}",
                "name": "slimtest__m__t",
                "status": "pass",
                "execution_time": 0.1,
            }
            for version in (1, 2)
        ]
        _fake_dbt(monkeypatch, results=results)
        result = unittest_project(project)
        assert result.ok
        assert result.summary.total == 2
        assert [entry.outcome.name for entry in result.outcomes] == [
            "slimtest__m__t",
            "slimtest__m__t",
        ]
        assert {entry.original_name for entry in result.outcomes} == {"t"}
