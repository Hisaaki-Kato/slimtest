"""Read dbt's manifest and preserve resource identities used by unit tests."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from .factory import SlimTestError

MANIFEST_RELATIVE_PATH = Path("target") / "manifest.json"
_REFABLE_RESOURCE_TYPES = frozenset({"model", "seed", "snapshot"})


@dataclass(frozen=True)
class UpstreamRef:
    """A manifest resource and the expression dbt expects for it."""

    kind: Literal["ref", "source"]
    name: str
    source_name: str | None = None
    package_name: str | None = None
    version: int | str | None = None
    unique_id: str | None = field(default=None, compare=False)

    def to_input_expression(self) -> str:
        """Render this identity without evaluating user-provided text."""
        if self.kind == "source":
            return f"source({self.source_name!r}, {self.name!r})"
        args = [repr(self.name)]
        if self.package_name is not None:
            args.insert(0, repr(self.package_name))
        if self.version is not None:
            args.append(f"version={self.version!r}")
        return f"ref({', '.join(args)})"


@dataclass(frozen=True)
class ManifestUnitTest:
    """A dbt unit-test node and its slimtest-generated logical name."""

    unique_id: str
    name: str
    depends_on: tuple[str, ...]
    package_name: str | None = None


class ManifestNotFoundError(SlimTestError):
    """No target manifest exists."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"manifest not found at {path}. Run `dbt parse` first.")
        self.path = path


class InvalidManifestError(SlimTestError):
    """The manifest exists but is malformed."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid manifest {path}: {detail}")
        self.path = path


class AmbiguousUpstreamError(SlimTestError):
    """An upstream name has more than one possible manifest identity."""

    def __init__(self, name: str, candidates: list[str]) -> None:
        super().__init__(
            f"upstream name {name!r} is ambiguous; candidates: {candidates}. "
            "Qualify the reference explicitly."
        )
        self.name = name
        self.candidates = candidates


@dataclass(frozen=True)
class Manifest:
    """The subset of dbt's manifest needed to compile and verify slimtest tests."""

    models: frozenset[str]
    sources_by_table: dict[str, list[str]]
    model_upstreams: dict[str, list[str]]
    refables_by_name: dict[str, tuple[UpstreamRef, ...]] = field(default_factory=dict)
    sources_by_name: dict[str, tuple[UpstreamRef, ...]] = field(default_factory=dict)
    upstreams_by_model_id: dict[str, tuple[UpstreamRef, ...]] = field(
        default_factory=dict
    )
    model_ids_by_name: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unit_tests: dict[str, ManifestUnitTest] = field(default_factory=dict)
    resources_by_id: dict[str, UpstreamRef] = field(default_factory=dict)
    project_name: str | None = None

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
        metadata = data.get("metadata")
        project_name = (
            metadata.get("project_name")
            if isinstance(metadata, dict)
            and isinstance(metadata.get("project_name"), str)
            else None
        )
        nodes = data.get("nodes") or {}
        if not isinstance(nodes, dict):
            nodes = {}
        sources = data.get("sources") or {}
        if not isinstance(sources, dict):
            sources = {}

        refs_by_name: dict[str, list[UpstreamRef]] = {}
        model_ids_by_name: dict[str, list[str]] = {}
        models: set[str] = set()
        resources_by_id: dict[str, UpstreamRef] = {}
        model_nodes: dict[str, dict[str, Any]] = {}

        for key, node in nodes.items():
            if not isinstance(key, str) or not isinstance(node, dict):
                continue
            resource_type = node.get("resource_type")
            name = node.get("name")
            if resource_type not in _REFABLE_RESOURCE_TYPES or not isinstance(
                name, str
            ):
                continue
            unique_id = node.get("unique_id")
            if not isinstance(unique_id, str):
                unique_id = key
            package_name = node.get("package_name")
            version = node.get("version")
            ref = UpstreamRef(
                kind="ref",
                name=name,
                package_name=package_name if isinstance(package_name, str) else None,
                version=version if isinstance(version, (int, str)) else None,
                unique_id=unique_id,
            )
            refs_by_name.setdefault(name, []).append(ref)
            resources_by_id[unique_id] = ref
            if resource_type == "model":
                models.add(name)
                model_ids_by_name.setdefault(name, []).append(unique_id)
                model_nodes[unique_id] = node

        sources_by_table: dict[str, list[str]] = {}
        source_refs_by_name: dict[str, list[UpstreamRef]] = {}
        for key, source in sources.items():
            if not isinstance(key, str) or not isinstance(source, dict):
                continue
            table = source.get("name")
            source_name = source.get("source_name")
            if not isinstance(table, str) or not isinstance(source_name, str):
                continue
            unique_id = source.get("unique_id")
            if not isinstance(unique_id, str):
                unique_id = key
            package_name = source.get("package_name")
            ref = UpstreamRef(
                kind="source",
                name=table,
                source_name=source_name,
                package_name=package_name if isinstance(package_name, str) else None,
                unique_id=unique_id,
            )
            source_refs_by_name.setdefault(table, []).append(ref)
            sources_by_table.setdefault(table, []).append(source_name)
            resources_by_id[unique_id] = ref

        upstreams_by_model_id: dict[str, tuple[UpstreamRef, ...]] = {}
        model_upstreams: dict[str, list[str]] = {}
        for model_id, node in model_nodes.items():
            refs = tuple(
                resources_by_id.get(node_id) or _fallback_ref_from_id(node_id)
                for node_id in _extract_dependency_ids(node)
            )
            upstreams_by_model_id[model_id] = refs
        for name, ids in model_ids_by_name.items():
            target_ids = _local_or_all_model_ids(ids, resources_by_id, project_name)
            model_upstreams[name] = _dedupe_names(
                tuple(
                    ref
                    for model_id in target_ids
                    for ref in upstreams_by_model_id.get(model_id, ())
                )
            )

        raw_unit_tests = data.get("unit_tests") or {}
        if not isinstance(raw_unit_tests, dict):
            raw_unit_tests = {}
        unit_tests: dict[str, ManifestUnitTest] = {}
        for key, entry in raw_unit_tests.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                continue
            unique_id = entry.get("unique_id")
            name = entry.get("name")
            if not isinstance(unique_id, str):
                unique_id = key
            if not isinstance(name, str) or not unique_id.startswith("unit_test."):
                continue
            unit_tests[unique_id] = ManifestUnitTest(
                unique_id=unique_id,
                name=name,
                depends_on=tuple(_extract_dependency_ids(entry)),
                package_name=(
                    entry.get("package_name")
                    if isinstance(entry.get("package_name"), str)
                    else None
                ),
            )

        return cls(
            models=frozenset(models),
            sources_by_table=sources_by_table,
            model_upstreams=model_upstreams,
            refables_by_name={k: tuple(v) for k, v in refs_by_name.items()},
            sources_by_name={k: tuple(v) for k, v in source_refs_by_name.items()},
            upstreams_by_model_id=upstreams_by_model_id,
            model_ids_by_name={k: tuple(v) for k, v in model_ids_by_name.items()},
            unit_tests=unit_tests,
            resources_by_id=resources_by_id,
            project_name=project_name,
        )

    def get_upstreams(self, model_name: str) -> list[str]:
        """Return bare dependency names for factory auto-fill compatibility."""
        return list(self.model_upstreams.get(model_name, []))

    def selected_unit_tests(
        self,
        test_names: list[str],
        model_names: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Map actual dbt unit-test IDs to selected generated names."""
        selected = set(test_names)
        return {
            unique_id: test.name
            for unique_id, test in self.unit_tests.items()
            if test.name in selected
            and (
                self.project_name is None
                or test.package_name is None
                or test.package_name == self.project_name
            )
            and self._unit_test_targets_model(test, model_names)
        }

    def _unit_test_targets_model(
        self, test: ManifestUnitTest, model_names: dict[str, str] | None
    ) -> bool:
        if model_names is None or test.name not in model_names:
            return True
        expected_model = model_names[test.name]
        return any(
            dependency in self.model_ids_by_name.get(expected_model, ())
            for dependency in test.depends_on
        )

    def resolve(self, name: str, *, model_name: str | None = None) -> UpstreamRef:
        """Resolve an explicit expression or a bare upstream in model scope."""
        explicit = parse_input_expression(name)
        if explicit is not None:
            return explicit
        scoped = self._scoped_candidates(name, model_name)
        if scoped:
            return self._one(name, scoped)
        candidates = [
            *self.refables_by_name.get(name, ()),
            *self.sources_by_name.get(name, ()),
        ]
        if not candidates:
            return UpstreamRef(kind="ref", name=name)
        return self._one(name, candidates)

    def dependency_name(self, value: str, *, model_name: str) -> str:
        """Return the manifest name represented by a bare or explicit input."""
        return self.resolve(value, model_name=model_name).name

    def upstream_matches(self, model_name: str, expected: str, given_key: str) -> bool:
        """Whether two input spellings identify the same model dependency."""
        expected_refs = self._scoped_candidates(expected, model_name)
        if not expected_refs:
            expected_refs = [self.resolve(expected, model_name=model_name)]

        explicit_given = parse_input_expression(given_key)
        if explicit_given is not None:
            given_refs = [explicit_given]
        else:
            given_refs = self._scoped_candidates(given_key, model_name)
            if not given_refs:
                given_refs = [self.resolve(given_key, model_name=model_name)]
        return any(
            _refs_match(expected_ref, given_ref)
            for expected_ref in expected_refs
            for given_ref in given_refs
        )

    def _scoped_candidates(
        self, name: str, model_name: str | None
    ) -> list[UpstreamRef]:
        if model_name is None:
            return []
        ids = list(self.model_ids_by_name.get(model_name, ()))
        model_ids = _local_or_all_model_ids(
            ids, self.resources_by_id, self.project_name
        )
        candidates = [
            ref
            for model_id in model_ids
            for ref in self.upstreams_by_model_id.get(model_id, ())
            if ref.name == name
        ]
        return list(dict.fromkeys(candidates))

    @staticmethod
    def _one(name: str, candidates: list[UpstreamRef]) -> UpstreamRef:
        if len(candidates) == 1:
            return candidates[0]
        rendered = [candidate.to_input_expression() for candidate in candidates]
        raise AmbiguousUpstreamError(name, rendered)


def _local_or_all_model_ids(
    ids: list[str], resources: dict[str, UpstreamRef], project_name: str | None
) -> list[str]:
    local = [
        node_id
        for node_id in ids
        if project_name is not None
        and resources.get(node_id) is not None
        and resources[node_id].package_name == project_name
    ]
    return local or ids


def _extract_dependency_ids(node: dict[str, Any]) -> list[str]:
    depends_on = node.get("depends_on")
    if not isinstance(depends_on, dict):
        return []
    raw_nodes = depends_on.get("nodes")
    if not isinstance(raw_nodes, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for node_id in raw_nodes:
        if isinstance(node_id, str) and node_id and node_id not in seen:
            seen.add(node_id)
            result.append(node_id)
    return result


def _fallback_ref_from_id(unique_id: str) -> UpstreamRef:
    """Keep legacy partial manifests useful without misreading real nodes."""
    parts = unique_id.split(".")
    if len(parts) >= 4 and parts[0] == "source":
        return UpstreamRef(
            kind="source",
            source_name=parts[-2],
            name=parts[-1],
            package_name=parts[1],
            unique_id=unique_id,
        )
    name = parts[-1]
    version: int | str | None = None
    if len(parts) >= 4 and parts[0] in _REFABLE_RESOURCE_TYPES:
        version_token = parts[-1]
        if version_token.startswith("v") and version_token[1:].isdigit():
            name = parts[-2]
            version = int(version_token[1:])
    return UpstreamRef(
        kind="ref",
        name=name,
        version=version,
        unique_id=unique_id,
    )


def _dedupe_names(refs: tuple[UpstreamRef, ...]) -> list[str]:
    return list(dict.fromkeys(ref.name for ref in refs))


def _refs_match(expected: UpstreamRef, given: UpstreamRef) -> bool:
    if expected.kind != given.kind or expected.name != given.name:
        return False
    if expected.kind == "source":
        return expected.source_name == given.source_name
    package_matches = (
        expected.package_name == given.package_name
        or expected.package_name is None
        or given.package_name is None
    )
    version_matches = (
        expected.version == given.version
        or expected.version is None
        or given.version is None
    )
    return package_matches and version_matches


def parse_input_expression(value: str) -> UpstreamRef | None:
    """Parse supported ref/source calls using AST validation, never eval."""
    stripped = value.strip()
    if not (stripped.startswith("ref(") or stripped.startswith("source(")):
        return None
    try:
        parsed = ast.parse(stripped, mode="eval").body
    except SyntaxError as exc:
        raise SlimTestError(
            f"invalid upstream expression {value!r}: {exc.msg}"
        ) from exc
    if not isinstance(parsed, ast.Call) or not isinstance(parsed.func, ast.Name):
        raise SlimTestError(f"invalid upstream expression {value!r}")
    if parsed.func.id == "source":
        if parsed.keywords or len(parsed.args) != 2:
            raise SlimTestError(f"source() requires two string arguments: {value!r}")
        args = [_literal_string(arg, value) for arg in parsed.args]
        return UpstreamRef(kind="source", source_name=args[0], name=args[1])
    if parsed.func.id != "ref" or len(parsed.args) not in (1, 2):
        raise SlimTestError(f"ref() requires one or two string arguments: {value!r}")
    args = [_literal_string(arg, value) for arg in parsed.args]
    version: int | str | None = None
    for keyword in parsed.keywords:
        if keyword.arg not in ("version", "v") or version is not None:
            raise SlimTestError(f"unsupported ref() argument in {value!r}")
        if not isinstance(keyword.value, ast.Constant) or type(
            keyword.value.value
        ) not in (int, str):
            raise SlimTestError(
                f"ref() version must be an integer or string: {value!r}"
            )
        version = cast(int | str, keyword.value.value)
    return UpstreamRef(
        kind="ref",
        package_name=args[0] if len(args) == 2 else None,
        name=args[-1],
        version=version,
    )


def _literal_string(node: ast.expr, expression: str) -> str:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        raise SlimTestError(f"upstream arguments must be strings: {expression!r}")
    return node.value


def try_load_manifest(project_root: Path) -> Manifest | None:
    """Best-effort load: return None if the file is missing."""
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
    "ManifestUnitTest",
    "UpstreamRef",
    "parse_input_expression",
    "try_load_manifest",
]
