"""Tests for `lighttest.result_parser`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lighttest.result_parser import (
    InvalidRunResultsError,
    load_run_results,
    summarize,
)
from lighttest.result_parser import TestOutcome as _Outcome


def _write_results(project_root: Path, results: list[dict]) -> Path:
    target = project_root / "target"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "run_results.json"
    path.write_text(json.dumps({"results": results}), encoding="utf-8")
    return path


def _unit_test(name: str, status: str = "pass", message: str | None = None) -> dict:
    return {
        "unique_id": f"unit_test.proj.model.{name}",
        "status": status,
        "execution_time": 0.42,
        "message": message,
    }


# -- load_run_results ------------------------------------------------


class TestLoadRunResults:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(InvalidRunResultsError):
            load_run_results(tmp_path)

    def test_malformed_json_raises(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        (target / "run_results.json").write_text("not json{", encoding="utf-8")
        with pytest.raises(InvalidRunResultsError):
            load_run_results(tmp_path)

    def test_missing_results_key_raises(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        (target / "run_results.json").write_text("{}", encoding="utf-8")
        with pytest.raises(InvalidRunResultsError):
            load_run_results(tmp_path)

    def test_empty_results_returns_empty_list(self, tmp_path):
        _write_results(tmp_path, [])
        assert load_run_results(tmp_path) == []

    def test_only_unit_test_rows_are_returned(self, tmp_path):
        _write_results(
            tmp_path,
            [
                _unit_test("test_a", "pass"),
                {
                    "unique_id": "test.proj.data_test_x",
                    "status": "pass",
                    "execution_time": 0.1,
                },
                _unit_test("test_b", "fail"),
                {
                    "unique_id": "model.proj.some_model",
                    "status": "success",
                    "execution_time": 0.5,
                },
            ],
        )
        outcomes = load_run_results(tmp_path)
        assert [o.name for o in outcomes] == ["test_a", "test_b"]

    def test_status_and_message_are_preserved(self, tmp_path):
        _write_results(
            tmp_path,
            [_unit_test("failed", "fail", message="row count mismatch")],
        )
        outcomes = load_run_results(tmp_path)
        assert outcomes[0] == _Outcome(
            unique_id="unit_test.proj.model.failed",
            name="failed",
            status="fail",
            execution_time=0.42,
            message="row count mismatch",
        )

    def test_unknown_status_rows_are_dropped(self, tmp_path):
        _write_results(
            tmp_path,
            [
                _unit_test("a", "pass"),
                _unit_test("b", "some_new_status"),
            ],
        )
        outcomes = load_run_results(tmp_path)
        assert [o.name for o in outcomes] == ["a"]

    def test_unique_id_without_unit_test_prefix_is_dropped(self, tmp_path):
        _write_results(
            tmp_path,
            [
                {
                    "unique_id": "unit_test.proj.model.kept",
                    "status": "pass",
                    "execution_time": 0.0,
                },
                {
                    "unique_id": "model.proj.dropped",
                    "status": "pass",
                    "execution_time": 0.0,
                },
            ],
        )
        outcomes = load_run_results(tmp_path)
        assert [o.name for o in outcomes] == ["kept"]


# -- summarize -------------------------------------------------------


class TestSummarize:
    def test_counts_each_status(self):
        outcomes = [
            _Outcome("a", "a", "pass", 0.1),
            _Outcome("b", "b", "pass", 0.1),
            _Outcome("c", "c", "fail", 0.1),
            _Outcome("d", "d", "error", 0.1),
            _Outcome("e", "e", "skipped", 0.1),
        ]
        summary = summarize(outcomes)
        assert summary.total == 5
        assert summary.passed == 2
        assert summary.failed == 1
        assert summary.errored == 1
        assert summary.skipped == 1

    def test_ok_is_true_when_no_fail_or_error(self):
        summary = summarize([_Outcome("a", "a", "pass", 0.1)])
        assert summary.ok is True

    def test_ok_is_false_with_a_failure(self):
        summary = summarize([_Outcome("a", "a", "fail", 0.1)])
        assert summary.ok is False

    def test_ok_is_false_with_an_error(self):
        summary = summarize([_Outcome("a", "a", "error", 0.1)])
        assert summary.ok is False
