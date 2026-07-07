"""Shared pytest fixtures for slimtest tests."""

from __future__ import annotations

# Set BEFORE importing anything that transitively loads rich / typer.
# Rich's Console picks up COLUMNS at first construction, which happens
# when Typer builds its help renderer -- so setting these via
# `CliRunner.invoke(env=...)` at test time is too late in some CI
# runners. NO_COLOR strips ANSI escapes so substring assertions on
# help output stay robust across Rich versions.
import os

os.environ.setdefault("COLUMNS", "200")
os.environ.setdefault("NO_COLOR", "1")

import textwrap  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def write_yaml(tmp_path: Path):
    """Return a helper that writes a dedented YAML string under `tmp_path`.

    Example:
        path = write_yaml("factories/users.yml", '''
            factories:
              user:
                base:
                  id: 1
        ''')
    """

    def _write(relative: str, content: str) -> Path:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        return path

    return _write
