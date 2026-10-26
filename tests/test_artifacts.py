"""Tests for generated-artifact ownership and temporary hiding."""

from __future__ import annotations

from pathlib import Path

import pytest

import slimtest.artifacts as artifact_module
from slimtest.artifacts import (
    GENERATED_HEADER,
    ArtifactOwnershipError,
    ArtifactPublishError,
    publish_artifacts,
    temporarily_hide_generated_yml,
)


def test_hide_restores_old_generated_yml_without_commit(tmp_path: Path):
    output = tmp_path / "target/slimtest"
    publish_artifacts(
        output,
        {
            "old.generated.yml": GENERATED_HEADER + "version: 2\nunit_tests: []\n",
            "source_map.json": "{}\n",
        },
    )
    old = output / "old.generated.yml"

    with temporarily_hide_generated_yml(tmp_path):
        assert not old.exists()

    assert old.read_text(encoding="utf-8").startswith(GENERATED_HEADER)


def test_hide_commit_discards_old_yaml_and_keeps_replacement(tmp_path: Path):
    output = tmp_path / "target/slimtest"
    publish_artifacts(
        output,
        {
            "old.generated.yml": GENERATED_HEADER + "version: 2\nunit_tests: []\n",
            "source_map.json": "{}\n",
        },
    )

    with temporarily_hide_generated_yml(tmp_path) as hidden:
        publish_artifacts(
            output,
            {
                "new.generated.yml": (
                    GENERATED_HEADER + "version: 2\nunit_tests: []\n"
                ),
                "source_map.json": "{}\n",
            },
        )
        hidden.commit()

    assert not (output / "old.generated.yml").exists()
    assert (output / "new.generated.yml").exists()


def test_publish_refuses_generated_name_owned_by_user(tmp_path: Path):
    output = tmp_path / "target/slimtest"
    output.mkdir(parents=True)
    user_file = output / "model.generated.yml"
    user_file.write_text("version: 2\nmodels: []\n", encoding="utf-8")

    with pytest.raises(ArtifactOwnershipError):
        publish_artifacts(
            output,
            {
                "model.generated.yml": (
                    GENERATED_HEADER + "version: 2\nunit_tests: []\n"
                ),
                "source_map.json": "{}\n",
            },
        )

    assert user_file.read_text(encoding="utf-8") == "version: 2\nmodels: []\n"


def test_incomplete_publish_rollback_retains_recovery_backup(
    tmp_path: Path, monkeypatch
):
    output = tmp_path / "target/slimtest"
    publish_artifacts(
        output,
        {
            "old.generated.yml": GENERATED_HEADER + "version: 2\nunit_tests: []\n",
            "source_map.json": "{}\n",
        },
    )
    real_replace = artifact_module._replace_path

    def fail_install_and_restore(source: Path, destination: Path):
        if "slimtest-stage" in source.parent.name and source.name == "source_map.json":
            raise OSError("install failed")
        if "slimtest-backup" in source.parent.name:
            raise OSError("restore failed")
        real_replace(source, destination)

    monkeypatch.setattr(artifact_module, "_replace_path", fail_install_and_restore)

    with pytest.raises(ArtifactPublishError) as exc_info:
        publish_artifacts(
            output,
            {
                "new.generated.yml": (
                    GENERATED_HEADER + "version: 2\nunit_tests: []\n"
                ),
                "source_map.json": '{"new": {}}\n',
            },
        )

    assert "restoration is incomplete" in str(exc_info.value)
    assert exc_info.value.recovery_dir is not None
    assert exc_info.value.recovery_dir.is_dir()
    assert any(exc_info.value.recovery_dir.iterdir())


def test_incomplete_hide_restore_retains_recovery_backup(tmp_path: Path, monkeypatch):
    output = tmp_path / "target/slimtest"
    publish_artifacts(
        output,
        {
            "old.generated.yml": GENERATED_HEADER + "version: 2\nunit_tests: []\n",
            "source_map.json": "{}\n",
        },
    )
    real_replace = artifact_module._replace_path

    def fail_restore(source: Path, destination: Path):
        if "slimtest-hidden" in source.parent.name:
            raise OSError("restore failed")
        real_replace(source, destination)

    monkeypatch.setattr(artifact_module, "_replace_path", fail_restore)

    with (
        pytest.raises(ArtifactPublishError) as exc_info,
        temporarily_hide_generated_yml(tmp_path),
    ):
        pass

    assert "restoration is incomplete" in str(exc_info.value)
    assert exc_info.value.recovery_dir is not None
    assert (exc_info.value.recovery_dir / "old.generated.yml").exists()
