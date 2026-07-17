"""Parse dbt model yml files to extract slimtest unit_test blocks.

Walks `<project_root>/models/**/*.{yml,yaml}`, locates every
`models[*].meta.slimtest.unit_tests` entry, validates it against the
pydantic schema, and pairs it with its source line number (used later
for the source-map / failure reporting).

We use ruamel.yaml's round-trip mode purely to get line numbers off the
loaded objects; we still hand the data to pydantic for validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .factory import SlimTestError
from .schema import ModelSlimTest, ScenarioSpec, UnitTestSpec


@dataclass(frozen=True)
class ParsedUnitTest:
    """A unit test extracted from a model yml, with source-location info.

    `source_path` is relative to the project root. `source_line` is the
    1-indexed line where the unit-test mapping begins, or 0 if ruamel
    could not surface it (defensive fallback -- should be rare).

    `scenarios` is the dict of scenarios declared on the enclosing
    `meta.slimtest.scenarios` block; the compile layer resolves
    `spec.scenario` against it.
    """

    spec: UnitTestSpec
    model_name: str
    source_path: Path
    source_line: int
    scenarios: dict[str, ScenarioSpec] = field(default_factory=dict)


class InvalidModelYmlError(SlimTestError):
    """A model yml file failed to parse or its meta.slimtest block was invalid."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid model yml {path}: {detail}")
        self.path = path


def _rt_yaml() -> YAML:
    yaml = YAML(typ="rt")
    # dbt's yml loader tolerates duplicate keys (last value wins). ruamel is
    # strict by default and raises DuplicateKeyError. We relax it so a file
    # that dbt happily loads doesn't abort slimtest compile. Note: ruamel keeps
    # the *first* value here (dbt keeps the last), but slimtest only reads the
    # `meta.slimtest` subtree, and real-world duplicates live elsewhere (e.g.
    # Lightdash `meta.dimension` copy-paste), so the divergence is inert.
    yaml.allow_duplicate_keys = True
    return yaml


def parse_model_yml(path: Path, project_root: Path) -> list[ParsedUnitTest]:
    """Parse one yml file and return its slimtest unit tests.

    Files that have no `models:` key, or no model with
    `meta.slimtest.unit_tests`, return `[]`. Malformed YAML or invalid
    slimtest blocks raise `InvalidModelYmlError`.
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

        slimtest_block = (model_entry.get("meta") or {}).get("slimtest") or {}
        unit_tests_raw = slimtest_block.get("unit_tests")
        if not unit_tests_raw:
            continue

        # Plain-dict copies for pydantic; ruamel objects validate fine
        # but the conversion drops ruamel state from pydantic's stored
        # copies (we still keep the raw object around for line numbers).
        try:
            block = ModelSlimTest.model_validate(
                {
                    "scenarios": _to_plain_dict(slimtest_block.get("scenarios") or {}),
                    "unit_tests": [_to_plain_dict(t) for t in unit_tests_raw],
                }
            )
        except Exception as exc:  # noqa: BLE001 -- pydantic ValidationError
            raise InvalidModelYmlError(
                path,
                f"models[{model_idx}].meta.slimtest is not valid: {exc}",
            ) from exc

        for test_idx, spec in enumerate(block.unit_tests):
            line = _line_of_sequence_item(unit_tests_raw, test_idx)
            result.append(
                ParsedUnitTest(
                    spec=spec,
                    model_name=model_name,
                    source_path=rel_path,
                    source_line=line,
                    scenarios=block.scenarios,
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


def find_slimtest_tests(
    project_root: Path,
    model_paths: list[str] | None = None,
    *,
    skipped_files: list[Path] | None = None,
) -> list[ParsedUnitTest]:
    """Parse every model yml under the project's model_paths.

    A file that fails to parse only aborts discovery if it actually
    declares slimtest tests (its text mentions `slimtest`). Unrelated
    files -- existing lint debt like trailing tabs, or duplicate keys dbt
    would have tolerated -- are skipped so their problems don't block a
    compile that has nothing to do with them. Each skipped path is
    appended to `skipped_files` (when provided) for the caller to report.
    """
    collected: list[ParsedUnitTest] = []
    for yml_path in find_model_ymls(project_root, model_paths):
        try:
            collected.extend(parse_model_yml(yml_path, project_root))
        except InvalidModelYmlError:
            if _mentions_slimtest(yml_path):
                raise
            if skipped_files is not None:
                skipped_files.append(yml_path)
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


def _mentions_slimtest(path: Path) -> bool:
    """True if the file's raw text references `slimtest` at all.

    A cheap textual probe used to decide whether a parse failure is worth
    aborting for. If the file can't even be read, we err on the side of
    surfacing the failure (treat it as relevant).
    """
    try:
        return "slimtest" in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True


def _safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _to_plain_dict(value: Any) -> Any:
    """Recursively unwrap ruamel CommentedMap / CommentedSeq into plain dict/list.

    Pydantic validation works on ruamel types directly, but keeping the
    plain form simplifies downstream `==` comparisons and serialisation.
    """
    if isinstance(value, dict):
        return {k: _to_plain_dict(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain_dict(v) for v in value]
    return value


__all__ = [
    "InvalidModelYmlError",
    "ParsedUnitTest",
    "find_slimtest_tests",
    "find_model_ymls",
    "parse_model_yml",
]
