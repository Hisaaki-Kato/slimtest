"""CLI smoke tests using typer's `CliRunner`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from lighttest import __version__
from lighttest.cli import app


def _run(*args: str):
    return CliRunner().invoke(app, list(args))


class TestRootCommand:
    def test_no_args_prints_help(self):
        result = _run()
        # typer exits 2 for "missing command" and prints help.
        assert result.exit_code in (0, 2)
        assert "lighttest" in result.output.lower()

    def test_help_flag_succeeds(self):
        result = _run("--help")
        assert result.exit_code == 0
        assert "compile" in result.output
        assert "unittest" in result.output

    def test_version_flag(self):
        result = _run("--version")
        assert result.exit_code == 0
        assert __version__ in result.output


class TestCompileCommand:
    def test_compile_help(self):
        result = _run("compile", "--help")
        assert result.exit_code == 0
        assert "--project-dir" in result.output
        assert "--select" in result.output

    def test_compile_empty_project_succeeds(self, tmp_path: Path):
        # No models/, no factories -- valid, just produces zero tests.
        result = _run("compile", "--project-dir", str(tmp_path))
        assert result.exit_code == 0
        assert "compiled 0 test(s)" in result.output

    def test_compile_reports_generated_paths(self, tmp_path: Path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "m.yml").write_text(
            "models:\n"
            "  - name: m\n"
            "    meta:\n"
            "      lighttest:\n"
            "        unit_tests:\n"
            "          - {name: t, given: {u: [{x: 1}]}, expect: []}\n",
            encoding="utf-8",
        )
        result = _run("compile", "--project-dir", str(tmp_path))
        assert result.exit_code == 0
        assert "compiled 1 test(s)" in result.output
        assert "m.generated.yml" in result.output
        assert "source_map.json" in result.output


class TestUnittestCommand:
    def test_unittest_help(self):
        result = _run("unittest", "--help")
        assert result.exit_code == 0
        assert "--project-dir" in result.output

    def test_unittest_reports_summary_and_exits_zero_on_success(
        self, monkeypatch, tmp_path: Path
    ):
        # Mock the whole runner so we don't need dbt installed.
        from lighttest.compile import CompileResult
        from lighttest.dbt_runner import DbtResult
        from lighttest.result_parser import TestOutcome, TestSummary
        from lighttest.runner import EnrichedOutcome, UnittestResult
        from lighttest.schema import LightTestConfig

        compile_result = CompileResult(
            project_root=tmp_path,
            config=LightTestConfig(),
            output_dir=tmp_path / "target/lighttest",
            generated_files=[],
            source_map_path=tmp_path / "target/lighttest/source_map.json",
            source_map={},
            test_names=["lighttest__m__t"],
            warnings=[],
        )
        fake = UnittestResult(
            compile=compile_result,
            parse_result=DbtResult(0, "", ""),
            test_result=DbtResult(0, "", ""),
            outcomes=[
                EnrichedOutcome(
                    outcome=TestOutcome(
                        unique_id="unit_test.proj.m.lighttest__m__t",
                        name="lighttest__m__t",
                        status="pass",
                        execution_time=0.1,
                    ),
                    source_file=Path("models/m.yml"),
                    source_line=10,
                    original_name="t",
                )
            ],
            summary=TestSummary(total=1, passed=1, failed=0, errored=0, skipped=0),
        )
        monkeypatch.setattr("lighttest.cli.unittest_project", lambda _root, **_kw: fake)
        result = _run("unittest", "--project-dir", str(tmp_path))
        assert result.exit_code == 0
        assert "1/1 passed" in result.output

    def test_unittest_exits_one_when_a_test_fails(self, monkeypatch, tmp_path: Path):
        from lighttest.compile import CompileResult
        from lighttest.dbt_runner import DbtResult
        from lighttest.result_parser import TestOutcome, TestSummary
        from lighttest.runner import EnrichedOutcome, UnittestResult
        from lighttest.schema import LightTestConfig

        compile_result = CompileResult(
            project_root=tmp_path,
            config=LightTestConfig(),
            output_dir=tmp_path / "target/lighttest",
            generated_files=[],
            source_map_path=tmp_path / "target/lighttest/source_map.json",
            source_map={},
            test_names=["lighttest__m__t"],
            warnings=[],
        )
        fake = UnittestResult(
            compile=compile_result,
            parse_result=DbtResult(0, "", ""),
            test_result=DbtResult(1, "", ""),
            outcomes=[
                EnrichedOutcome(
                    outcome=TestOutcome(
                        unique_id="unit_test.proj.m.lighttest__m__t",
                        name="lighttest__m__t",
                        status="fail",
                        execution_time=0.1,
                        message="row count mismatch",
                    ),
                    source_file=Path("models/m.yml"),
                    source_line=42,
                    original_name="t",
                )
            ],
            summary=TestSummary(total=1, passed=0, failed=1, errored=0, skipped=0),
        )
        monkeypatch.setattr("lighttest.cli.unittest_project", lambda _root, **_kw: fake)
        result = _run("unittest", "--project-dir", str(tmp_path))
        assert result.exit_code == 1
        # Failure is rendered with source location.
        assert "FAIL: t" in result.output
        assert "models/m.yml:42" in result.output
