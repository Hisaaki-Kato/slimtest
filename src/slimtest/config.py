"""Loader for `slimtest.yml`.

The config file is optional. When absent, defaults from `SlimTestConfig`
are used.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from .factory import SlimTestError
from .schema import SlimTestConfig

CONFIG_FILENAME = "slimtest.yml"


class InvalidConfigError(SlimTestError):
    """`slimtest.yml` exists but is malformed or fails schema validation."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid {path}: {detail}")
        self.path = path


def load_config(project_root: Path) -> SlimTestConfig:
    """Load `<project_root>/slimtest.yml` or return defaults.

    A missing file is not an error -- the MVP defaults are usable as-is.
    A present but malformed file raises `InvalidConfigError`.
    """
    config_path = project_root / CONFIG_FILENAME
    if not config_path.exists():
        return SlimTestConfig()

    yaml = YAML(typ="safe")
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            raw = yaml.load(fh)
    except Exception as exc:  # noqa: BLE001
        raise InvalidConfigError(config_path, str(exc)) from exc

    if raw is None:
        return SlimTestConfig()
    if not isinstance(raw, dict):
        raise InvalidConfigError(
            config_path, f"expected a mapping at top level, got {type(raw).__name__}"
        )

    try:
        return SlimTestConfig.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 -- pydantic ValidationError
        raise InvalidConfigError(config_path, str(exc)) from exc


__all__ = ["CONFIG_FILENAME", "InvalidConfigError", "load_config"]
