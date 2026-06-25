"""Shared pytest fixtures for lighttest tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


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
