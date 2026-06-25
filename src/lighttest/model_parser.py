"""Parse dbt model yml files to extract lighttest unit_test blocks.

Walks `<project_root>/models/**/*.{yml,yaml}`, locates every
`models[*].meta.lighttest.unit_tests` entry, validates it against the
pydantic schema, and pairs it with its source line number (used later
for the source-map / failure reporting).

We use ruamel.yaml's round-trip mode purely to get line numbers off the
loaded objects; we still hand the data to pydantic for validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .factory import LightTestError
from .schema import ModelLightTest, UnitTestSpec


@dataclass(frozen=True)
class ParsedUnitTest:
    """A unit test extracted from a model yml, with source-location info.

    `source_path` is relative to the project root. `source_line` is the
    1-indexed line where the unit-test mapping begins, or 0 if ruamel
    could not surface it (defensive fallback -- should be rare).
    """

    spec: UnitTestSpec
    model_name: str
    source_path: Path
    source_line: int


class InvalidModelYmlError(LightTestError):
    """A model yml file failed to parse or its meta.lighttest block was invalid."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid model yml {path}: {detail}")
        self.path = path


def _rt_yaml() -> YAML:
    return YAML(typ="rt")


def parse_model_yml(path: Path, project_root: Path) -> list[ParsedUnitTest]:
    """Parse one yml file and return its lighttest unit tests.

    Files that have no `models:` key, or no model with
    `meta.lighttest.unit_tests`, return `[]`. Malformed YAML or invalid
    lighttest blocks raise `InvalidModelYmlError`.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = _rt_yaml().load(fh)
    except Exception as exc:  # noqa: BLE001 -- ruamel raises broadly
        raise InvalidModelYmlError(path, str(exc)) from exc

    if data is None or not isinstance(data, dict):
        return []

    models = data.get("models")
    if not models:
        return []

    rel_path = _safe_relative(path, project_root)
    result: list[ParsedUnitTest] = []

    for model_idx, model_entry in enumerate(models):
        if not isinstance(model_entry, dict):
            continue
        model_name = model_entry.get("name")
        if not isinstance(model_name, str) or not model_name:
            continue

        unit_tests_raw = ((model_entry.get("meta") or {}).get("lighttest") or {}).get(
            "unit_tests"
        )
        if not unit_tests_raw:
            continue

        # Plain-dict copy for pydantic; ruamel objects validate fine but
        # the conversion drops ruamel state from pydantic's stored copies.
        try:
            block = ModelLightTest.model_validate(
                {"unit_tests": [dict(t) for t in unit_tests_raw]}
            )
        except Exception as exc:  # noqa: BLE001 -- pydantic ValidationError
            raise InvalidModelYmlError(
                path,
                f"models[{model_idx}].meta.lighttest is not valid: {exc}",
            ) from exc

        for test_idx, spec in enumerate(block.unit_tests):
            line = _line_of_sequence_item(unit_tests_raw, test_idx)
            result.append(
                ParsedUnitTest(
                    spec=spec,
                    model_name=model_name,
                    source_path=rel_path,
                    source_line=line,
                )
            )

    return result


def find_model_ymls(
    project_root: Path, model_paths: list[str] | None = None
) -> list[Path]:
    """All `*.yml` / `*.yaml` under each entry of `model_paths`.

    `model_paths` defaults to `["models"]` to mirror dbt's default. Paths
    that do not exist are silently skipped, since a fresh project may
    not have populated all of them yet.
    """
    paths = model_paths or ["models"]
    found: list[Path] = []
    for rel in paths:
        base = project_root / rel
        if not base.exists():
            continue
        for suffix in ("*.yml", "*.yaml"):
            found.extend(base.rglob(suffix))
    return sorted(set(found))


def find_lighttest_tests(
    project_root: Path, model_paths: list[str] | None = None
) -> list[ParsedUnitTest]:
    """Parse every model yml under the project's model_paths."""
    collected: list[ParsedUnitTest] = []
    for yml_path in find_model_ymls(project_root, model_paths):
        collected.extend(parse_model_yml(yml_path, project_root))
    return collected


# -- helpers -----------------------------------------------------------


def _line_of_sequence_item(sequence: Any, idx: int) -> int:
    """Return the 1-indexed line number of `sequence[idx]`, or 0 if unknown.

    Defensive: ruamel exposes `.lc.item(i)` on CommentedSeq, but plain
    lists (e.g. produced by `typ='safe'` accidentally) do not.
    """
    lc = getattr(sequence, "lc", None)
    if lc is None:
        return 0
    try:
        row, _col = lc.item(idx)
    except (AttributeError, KeyError, IndexError, TypeError):
        return 0
    return int(row) + 1


def _safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


__all__ = [
    "InvalidModelYmlError",
    "ParsedUnitTest",
    "find_lighttest_tests",
    "find_model_ymls",
    "parse_model_yml",
]
