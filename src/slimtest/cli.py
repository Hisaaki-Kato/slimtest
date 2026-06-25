"""slimtest CLI entry point.

`compile` is fully wired; `unittest` is still a stub pending the dbt
subprocess layer (next phase).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .compile import CompileResult, compile_project
from .factory import SlimTestError
from .runner import EnrichedOutcome, UnittestResult, unittest_project

app = typer.Typer(
    name="slimtest",
    help="Factory + trait DSL on top of dbt unit tests.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:  # noqa: FBT001 -- typer convention
    if value:
        typer.echo(__version__)
        raise typer.Exit


ProjectDirOption = Annotated[
    Path,
    typer.Option(
        "--project-dir",
        help="Path to the dbt project root (defaults to the current directory).",
    ),
]

SelectOption = Annotated[
    str | None,
    typer.Option(
        "--select",
        help="Subset of models or tests to compile/run (dbt-style selector).",
    ),
]


@app.callback()
def _root(
    version: Annotated[  # noqa: ARG001 -- handled by callback
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the slimtest version and exit.",
        ),
    ] = False,
) -> None:
    """Top-level CLI options."""


@app.command()
def compile(  # noqa: A001 -- shadowing builtin is fine for a CLI verb
    project_dir: ProjectDirOption = Path("."),
    select: SelectOption = None,
) -> None:
    """Expand slimtest extension YAML into standard dbt unit_tests YAML.

    Writes generated artefacts under `target/slimtest/` and does NOT
    invoke dbt. Intended for debugging and inspection.
    """
    try:
        result = compile_project(project_dir, select=select)
    except SlimTestError as exc:
        typer.echo(f"[slimtest] error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"[slimtest] compiled {result.test_count} test(s):")
    for path in result.generated_files:
        rel = path.relative_to(result.project_root)
        typer.echo(f"  -> {rel}")
    rel_map = result.source_map_path.relative_to(result.project_root)
    typer.echo(f"  -> {rel_map}")
    _print_warnings(result)


@app.command()
def unittest(
    project_dir: ProjectDirOption = Path("."),
    select: SelectOption = None,
) -> None:
    """Compile + run the resulting unit tests via `dbt test`."""
    try:
        result = unittest_project(project_dir, select=select)
    except SlimTestError as exc:
        typer.echo(f"[slimtest] error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _print_unittest_result(result)
    raise typer.Exit(code=0 if result.ok else 1)


# -- output helpers --------------------------------------------------


def _print_warnings(compile_result: CompileResult) -> None:
    for warning in compile_result.warnings:
        typer.echo(f"[slimtest] warning: {warning}", err=True)


def _print_unittest_result(result: UnittestResult) -> None:
    n = result.compile.test_count
    typer.echo(f"[slimtest] compiled {n} test(s)")
    _print_warnings(result.compile)

    if not result.parse_result.ok:
        typer.echo(
            f"[slimtest] warning: `dbt parse` exited {result.parse_result.exit_code}",
            err=True,
        )

    if n == 0:
        typer.echo("[slimtest] no slimtest tests to run.")
        return

    failed = [e for e in result.outcomes if e.outcome.status != "pass"]
    typer.echo(
        f"[slimtest] {result.summary.passed}/{result.summary.total} passed; "
        f"{result.summary.failed} failed, "
        f"{result.summary.errored} errored, "
        f"{result.summary.skipped} skipped."
    )

    for entry in failed:
        _print_failure(entry)

    if result.summary.total == 0 and not result.test_result.ok:
        # dbt failed before producing run_results.json -- surface stderr.
        typer.echo(result.test_result.stderr, err=True)


def _print_failure(entry: EnrichedOutcome) -> None:
    label = entry.original_name or entry.outcome.name
    if entry.source_file is not None and entry.source_line is not None:
        location = f"{entry.source_file}:{entry.source_line}"
    else:
        location = "<source location unknown>"
    typer.echo(
        f"  {entry.outcome.status.upper()}: {label}  ({location})",
        err=True,
    )
    if entry.outcome.message:
        for line in entry.outcome.message.splitlines():
            typer.echo(f"      {line}", err=True)


__all__ = ["app"]
