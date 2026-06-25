"""Read dbt's `target/manifest.json` and resolve upstream names.

The user writes upstream identifiers as bare table/model names in
`given:`. dbt's standard YAML, however, distinguishes between
`ref('model_name')` and `source('source_name', 'table_name')`. This
module loads the manifest and turns a bare name into the right call.

Resolution rules:

* In `models` only       -> ref
* In `sources` only      -> source
* In both                -> AmbiguousUpstreamError
* Multiple sources match -> AmbiguousUpstreamError
* In neither             -> fall back to ref (user gets a clear error
                            from dbt at run time)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .factory import LightTestError

MANIFEST_RELATIVE_PATH = Path("target") / "manifest.json"


@dataclass(frozen=True)
class UpstreamRef:
    """How to render an upstream identifier inside dbt yml."""

    kind: Literal["ref", "source"]
    name: str
    source_name: str | None = None

    def to_input_expression(self) -> str:
        """The Jinja-style expression dbt expects under `given[].input`."""
        if self.kind == "ref":
            return f"ref('{self.name}')"
        return f"source('{self.source_name}', '{self.name}')"


class ManifestNotFoundError(LightTestError):
    """No `target/manifest.json` was found under the project root."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"manifest not found at {path}. Run `dbt parse` first.")
        self.path = path


class InvalidManifestError(LightTestError):
    """`manifest.json` exists but is malformed."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid manifest {path}: {detail}")
        self.path = path


class AmbiguousUpstreamError(LightTestError):
    """A name appears as both a model and a source, or as multiple sources."""

    def __init__(self, name: str, candidates: list[str]) -> None:
        super().__init__(
            f"upstream name {name!r} is ambiguous; candidates: {candidates}. "
            "Rename one or qualify the reference."
        )
        self.name = name
        self.candidates = candidates


@dataclass(frozen=True)
class Manifest:
    """Slim view over dbt's manifest.json -- just what lighttest needs."""

    models: frozenset[str]
    # table_name -> list of source_name's that contain that table
    sources_by_table: dict[str, list[str]]
    # model_name -> ordered list of bare upstream names from depends_on.nodes
    model_upstreams: dict[str, list[str]]

    @classmethod
    def load(cls, project_root: Path) -> Manifest:
        """Load `<project_root>/target/manifest.json`."""
        manifest_path = project_root / MANIFEST_RELATIVE_PATH
        if not manifest_path.exists():
            raise ManifestNotFoundError(manifest_path)
        try:
            with manifest_path.open("r", encoding="utf-8") as fh:
                data: Any = json.load(fh)
        except Exception as exc:  # noqa: BLE001 -- json raises broadly
            raise InvalidManifestError(manifest_path, str(exc)) from exc

        if not isinstance(data, dict):
            raise InvalidManifestError(
                manifest_path,
                f"expected a JSON object at top level, got {type(data).__name__}",
            )
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Manifest:
        models: set[str] = set()
        model_upstreams: dict[str, list[str]] = {}
        for node in (data.get("nodes") or {}).values():
            if not isinstance(node, dict):
                continue
            if node.get("resource_type") != "model":
                continue
            name = node.get("name")
            if not isinstance(name, str) or not name:
                continue
            models.add(name)
            model_upstreams[name] = _extract_upstream_names(node)

        sources_by_table: dict[str, list[str]] = {}
        for source in (data.get("sources") or {}).values():
            if not isinstance(source, dict):
                continue
            table = source.get("name")
            source_name = source.get("source_name")
            if isinstance(table, str) and isinstance(source_name, str):
                sources_by_table.setdefault(table, []).append(source_name)

        return cls(
            models=frozenset(models),
            sources_by_table=sources_by_table,
            model_upstreams=model_upstreams,
        )

    def get_upstreams(self, model_name: str) -> list[str]:
        """Bare upstream names this model depends on, in declaration order.

        Returns `[]` for unknown models -- caller is expected to have
        already discovered the model some other way.
        """
        return list(self.model_upstreams.get(model_name, []))

    def resolve(self, name: str) -> UpstreamRef:
        """Resolve a bare upstream name to a `ref(...)` or `source(...)` expression."""
        in_models = name in self.models
        sources = self.sources_by_table.get(name, [])

        if in_models and sources:
            candidates = [f"ref('{name}')"] + [
                f"source('{s}', '{name}')" for s in sources
            ]
            raise AmbiguousUpstreamError(name, candidates)

        if in_models:
            return UpstreamRef(kind="ref", name=name)

        if sources:
            if len(sources) > 1:
                candidates = [f"source('{s}', '{name}')" for s in sources]
                raise AmbiguousUpstreamError(name, candidates)
            return UpstreamRef(kind="source", name=name, source_name=sources[0])

        # Unknown -> fall back to ref. dbt will produce a clear error at run
        # time if the model really doesn't exist.
        return UpstreamRef(kind="ref", name=name)


def _extract_upstream_names(node: dict[str, Any]) -> list[str]:
    """Pull bare upstream names from a model node's `depends_on.nodes`.

    `depends_on.nodes` entries look like `model.<proj>.<name>` or
    `source.<proj>.<source_name>.<table>`. The user writes bare names in
    `given:`, so we strip everything except the final segment.
    Duplicates are de-duped while preserving first-seen order.
    """
    depends_on = node.get("depends_on")
    if not isinstance(depends_on, dict):
        return []
    raw_nodes = depends_on.get("nodes")
    if not isinstance(raw_nodes, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for node_id in raw_nodes:
        if not isinstance(node_id, str) or "." not in node_id:
            continue
        bare = node_id.rsplit(".", 1)[-1]
        if not bare or bare in seen:
            continue
        seen.add(bare)
        result.append(bare)
    return result


def try_load_manifest(project_root: Path) -> Manifest | None:
    """Best-effort load: return None if the file is missing.

    Used by `compile` so a user can run it without first invoking dbt.
    """
    try:
        return Manifest.load(project_root)
    except ManifestNotFoundError:
        return None


__all__ = [
    "MANIFEST_RELATIVE_PATH",
    "AmbiguousUpstreamError",
    "InvalidManifestError",
    "Manifest",
    "ManifestNotFoundError",
    "UpstreamRef",
    "try_load_manifest",
]
