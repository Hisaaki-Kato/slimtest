"""Tests for `slimtest.dbt_project`."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from slimtest.dbt_project import (
    DEFAULT_MODEL_PATHS,
    DbtProject,
    InvalidDbtProjectError,
    check_generated_path_in_model_paths,
    load_dbt_project,
)


def _write_project(tmp_path: Path, body: str) -> None:
    (tmp_path / "dbt_project.yml").write_text(
        textwrap.dedent(body).lstrip(), encoding="utf-8"
    )


# -- load_dbt_project ---------------------------------------------


class TestLoadDbtProject:
    def test_missing_file_returns_none(self, tmp_path):
        assert load_dbt_project(tmp_path) is None

    def test_empty_file_uses_defaults(self, tmp_path):
        _write_project(tmp_path, "")
        project = load_dbt_project(tmp_path)
        assert project is not None
        assert project.model_paths == DEFAULT_MODEL_PATHS

    def test_explicit_model_paths(self, tmp_path):
        _write_project(
            tmp_path,
            """
            name: x
            model-paths: ["models", "target/slimtest"]
            """,
        )
        project = load_dbt_project(tmp_path)
        assert project is not None
        assert project.model_paths == ("models", "target/slimtest")

    def test_default_model_paths_when_omitted(self, tmp_path):
        _write_project(tmp_path, "name: x\n")
        project = load_dbt_project(tmp_path)
        assert project is not None
        assert project.model_paths == DEFAULT_MODEL_PATHS

    def test_malformed_yaml_raises(self, tmp_path):
        _write_project(tmp_path, "name: x\nmodel-paths: [oops")
        with pytest.raises(InvalidDbtProjectError):
            load_dbt_project(tmp_path)

    def test_non_mapping_top_level_raises(self, tmp_path):
        _write_project(tmp_path, "- a\n- b\n")
        with pytest.raises(InvalidDbtProjectError):
            load_dbt_project(tmp_path)

    def test_non_list_model_paths_raises(self, tmp_path):
        _write_project(tmp_path, "model-paths: just-a-string\n")
        with pytest.raises(InvalidDbtProjectError):
            load_dbt_project(tmp_path)

    def test_non_string_entry_in_model_paths_raises(self, tmp_path):
        _write_project(tmp_path, 'model-paths: ["models", 42]\n')
        with pytest.raises(InvalidDbtProjectError):
            load_dbt_project(tmp_path)


# -- check_generated_path_in_model_paths -------------------------


class TestCheckGeneratedPath:
    def _project(self, paths: tuple[str, ...]) -> DbtProject:
        return DbtProject(project_root=Path("."), model_paths=paths)

    def test_target_present_returns_none(self):
        project = self._project(("models", "target/slimtest"))
        assert check_generated_path_in_model_paths(project, "target/slimtest") is None

    def test_target_absent_returns_warning(self):
        project = self._project(("models",))
        warning = check_generated_path_in_model_paths(project, "target/slimtest")
        assert warning is not None
        assert "target/slimtest" in warning
        assert "model-paths" in warning

    def test_normalises_trailing_slash(self):
        project = self._project(("models", "target/slimtest/"))
        assert check_generated_path_in_model_paths(project, "target/slimtest") is None

    def test_normalises_dot_slash_prefix(self):
        project = self._project(("models", "./target/slimtest"))
        assert check_generated_path_in_model_paths(project, "target/slimtest") is None

    def test_custom_generated_path(self):
        project = self._project(("models", "build/lt"))
        assert check_generated_path_in_model_paths(project, "build/lt") is None
        assert check_generated_path_in_model_paths(project, "elsewhere") is not None
