"""Read `dbt_project.yml` for the bits slimtest needs.

Right now that's just `model-paths`, so we know whether `dbt` will
actually pick up the generated yml we wrote to `target/slimtest/`. If
it won't, the CLI surfaces a warning that walks the user through fixing
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .factory import SlimTestError

DBT_PROJECT_FILENAME = "dbt_project.yml"
DEFAULT_MODEL_PATHS: tuple[str, ...] = ("models",)


class InvalidDbtProjectError(SlimTestError):
    """`dbt_project.yml` exists but is malformed or has unexpected shape."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid {path}: {detail}")
        self.path = path


@dataclass(frozen=True)
class DbtProject:
    """Slim view over `dbt_project.yml`."""

    project_root: Path
    model_paths: tuple[str, ...]


def load_dbt_project(project_root: Path) -> DbtProject | None:
    """Load `<project_root>/dbt_project.yml`, or return None if absent.

    A missing file is not an error: `slimtest compile` works without
    dbt being present at all (debugging use case).
    """
    path = project_root / DBT_PROJECT_FILENAME
    if not path.exists():
        return None

    yaml = YAML(typ="safe")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data: Any = yaml.load(fh)
    except Exception as exc:  # noqa: BLE001
        raise InvalidDbtProjectError(path, str(exc)) from exc

    if data is None:
        return DbtProject(project_root=project_root, model_paths=DEFAULT_MODEL_PATHS)
    if not isinstance(data, dict):
        raise InvalidDbtProjectError(
            path, f"top level must be a mapping, got {type(data).__name__}"
        )

    raw_paths = data.get("model-paths", list(DEFAULT_MODEL_PATHS))
    if not isinstance(raw_paths, list):
        raise InvalidDbtProjectError(path, "`model-paths` must be a list")
    if not all(isinstance(p, str) for p in raw_paths):
        raise InvalidDbtProjectError(
            path, "every entry in `model-paths` must be a string"
        )

    return DbtProject(
        project_root=project_root,
        model_paths=tuple(raw_paths),
    )


def check_generated_path_in_model_paths(
    dbt_project: DbtProject, generated_yml_path: str
) -> str | None:
    """Return a warning string if `generated_yml_path` isn't in model-paths.

    The comparison normalises both sides via `Path()` so trailing
    slashes, `./` prefixes, etc. don't cause false negatives.
    """
    target = _normalise(generated_yml_path)
    known = {_normalise(p) for p in dbt_project.model_paths}
    if target in known:
        return None
    return (
        f"`{generated_yml_path}` is not in `model-paths` in dbt_project.yml -- "
        "dbt won't pick up the generated unit tests. Add it, e.g.:\n"
        f"    model-paths: [{', '.join(repr(p) for p in dbt_project.model_paths)}"
        f", {generated_yml_path!r}]"
    )


def _normalise(path: str) -> str:
    """Canonical string form so equivalent paths compare equal."""
    return str(Path(path))


__all__ = [
    "DBT_PROJECT_FILENAME",
    "DEFAULT_MODEL_PATHS",
    "DbtProject",
    "InvalidDbtProjectError",
    "check_generated_path_in_model_paths",
    "load_dbt_project",
]
