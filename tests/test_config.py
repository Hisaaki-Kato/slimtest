"""Tests for `slimtest.config.load_config`."""

from __future__ import annotations

import pytest

from slimtest.config import InvalidConfigError, load_config
from slimtest.schema import SlimTestConfig


def test_missing_file_returns_defaults(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg == SlimTestConfig()


def test_empty_file_returns_defaults(tmp_path):
    (tmp_path / "slimtest.yml").write_text("", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg == SlimTestConfig()


def test_partial_file_overrides_named_fields(tmp_path):
    (tmp_path / "slimtest.yml").write_text(
        "factories_path: tests/factories\n", encoding="utf-8"
    )
    cfg = load_config(tmp_path)
    assert cfg.factories_path == "tests/factories"
    assert cfg.generated_yml_path == "target/slimtest"  # default


def test_unknown_key_raises(tmp_path):
    (tmp_path / "slimtest.yml").write_text("bogus_key: 1\n", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        load_config(tmp_path)


def test_malformed_yaml_raises(tmp_path):
    (tmp_path / "slimtest.yml").write_text(
        "factories_path: [unclosed", encoding="utf-8"
    )
    with pytest.raises(InvalidConfigError):
        load_config(tmp_path)


def test_non_mapping_top_level_raises(tmp_path):
    (tmp_path / "slimtest.yml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        load_config(tmp_path)
