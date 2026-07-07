"""CLI smoke tests using typer's `CliRunner`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from slimtest import __version__
from slimtest.cli import app


def _run(*args: str):
    # Force a wide terminal so Typer's Rich-rendered `--help` output does
    # not soft-wrap options like `--project-dir` across lines; without
    # this, CI runners (COLUMNS=80) fail assertions that a locally-wide
    # terminal happens to pass. NO_COLOR strips ANSI escapes for good
    # measure so substring matches stay robust.
    return CliRunner().invoke(
        app,
        list(args),
        env={"COLUMNS": "200", "NO_COLOR": "1"},
    )


class TestRootCommand:
    def test_no_args_prints_help(self):
        result = _run()
        # typer exits 2 for "missing command" and prints help.
        assert result.exit_code in (0, 2)
        assert "slimtest" in result.output.lower()

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

    def test_compile_hides_info_notices_by_default(self, tmp_path: Path):
        # A factory-triggered auto-fill emits an INFO notice; default run
        # (no -v) must NOT surface it, so as not to look like a warning.
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "m.yml").write_text(
            "models:\n"
            "  - name: m\n"
            "    meta:\n"
            "      slimtest:\n"
            "        unit_tests:\n"
            "          - {name: t, given: {u: [{x: 1}]}, expect: []}\n",
            encoding="utf-8",
        )
        # Add a factory + fake manifest so auto-fill fires.
        (tmp_path / "tests/slimtest_factories").mkdir(parents=True)
        (tmp_path / "tests/slimtest_factories/extra.yml").write_text(
            "factories:\n  extra:\n    base: {y: 1}\n", encoding="utf-8"
        )
        target = tmp_path / "target"
        target.mkdir()
        (target / "manifest.json").write_text(
            '{"nodes": {"model.p.m": {"resource_type": "model", "name": "m", '
            '"depends_on": {"nodes": ["model.p.u", "model.p.extra"]}}}, '
            '"sources": {}}',
            encoding="utf-8",
        )

        default = _run("compile", "--project-dir", str(tmp_path))
        assert default.exit_code == 0
        assert "auto-injected" not in default.output

        verbose = _run("compile", "--project-dir", str(tmp_path), "--verbose")
        assert verbose.exit_code == 0
        assert "auto-injected" in verbose.output
        assert "info:" in verbose.output

    def test_compile_reports_generated_paths(self, tmp_path: Path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "m.yml").write_text(
            "models:\n"
            "  - name: m\n"
            "    meta:\n"
            "      slimtest:\n"
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
        from slimtest.compile import CompileResult
        from slimtest.dbt_runner import DbtResult
        from slimtest.result_parser import TestOutcome, TestSummary
        from slimtest.runner import EnrichedOutcome, UnittestResult
        from slimtest.schema import SlimTestConfig

        compile_result = CompileResult(
            project_root=tmp_path,
            config=SlimTestConfig(),
            output_dir=tmp_path / "target/slimtest",
            generated_files=[],
            source_map_path=tmp_path / "target/slimtest/source_map.json",
            source_map={},
            test_names=["slimtest__m__t"],
            warnings=[],
            notices=[],
        )
        fake = UnittestResult(
            compile=compile_result,
            parse_result=DbtResult(0, "", ""),
            test_result=DbtResult(0, "", ""),
            outcomes=[
                EnrichedOutcome(
                    outcome=TestOutcome(
                        unique_id="unit_test.proj.m.slimtest__m__t",
                        name="slimtest__m__t",
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
        monkeypatch.setattr("slimtest.cli.unittest_project", lambda _root, **_kw: fake)
        result = _run("unittest", "--project-dir", str(tmp_path))
        assert result.exit_code == 0
        assert "1/1 passed" in result.output

    def test_unittest_exits_one_when_a_test_fails(self, monkeypatch, tmp_path: Path):
        from slimtest.compile import CompileResult
        from slimtest.dbt_runner import DbtResult
        from slimtest.result_parser import TestOutcome, TestSummary
        from slimtest.runner import EnrichedOutcome, UnittestResult
        from slimtest.schema import SlimTestConfig

        compile_result = CompileResult(
            project_root=tmp_path,
            config=SlimTestConfig(),
            output_dir=tmp_path / "target/slimtest",
            generated_files=[],
            source_map_path=tmp_path / "target/slimtest/source_map.json",
            source_map={},
            test_names=["slimtest__m__t"],
            warnings=[],
            notices=[],
        )
        fake = UnittestResult(
            compile=compile_result,
            parse_result=DbtResult(0, "", ""),
            test_result=DbtResult(1, "", ""),
            outcomes=[
                EnrichedOutcome(
                    outcome=TestOutcome(
                        unique_id="unit_test.proj.m.slimtest__m__t",
                        name="slimtest__m__t",
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
        monkeypatch.setattr("slimtest.cli.unittest_project", lambda _root, **_kw: fake)
        result = _run("unittest", "--project-dir", str(tmp_path))
        assert result.exit_code == 1
        # Failure is rendered with source location.
        assert "FAIL: t" in result.output
        assert "models/m.yml:42" in result.output
