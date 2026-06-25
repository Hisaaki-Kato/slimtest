"""Factory registry + resolution.

A registry holds all factories discovered under a directory tree. Names
must be globally unique across all files in that tree; collisions raise
at load time.

Resolution turns a `(factory_name, trait_name, override)` triple into a
final row dict by deep-merging in the order: base -> trait -> override.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .deep_merge import deep_merge
from .schema import Factory, FactoryFile


class SlimTestError(Exception):
    """Base class for all slimtest user-facing errors."""


class DuplicateFactoryError(SlimTestError):
    """A factory name was defined in more than one file."""

    def __init__(self, name: str, first: Path, second: Path) -> None:
        super().__init__(
            f"factory {name!r} is defined in both {first} and {second}; "
            "factory names must be unique across the registry"
        )
        self.name = name
        self.first = first
        self.second = second


class UnknownFactoryError(SlimTestError):
    """A row referenced a `factory:` name that is not in the registry."""

    def __init__(self, name: str, known: Iterable[str]) -> None:
        known_sorted = sorted(known)
        super().__init__(f"unknown factory {name!r}; known factories: {known_sorted}")
        self.name = name


class UnknownTraitError(SlimTestError):
    """A row referenced a `trait:` that does not exist on the factory."""

    def __init__(self, factory: str, trait: str, known: Iterable[str]) -> None:
        known_sorted = sorted(known)
        super().__init__(
            f"factory {factory!r} has no trait {trait!r}; known traits: {known_sorted}"
        )
        self.factory = factory
        self.trait = trait


class InvalidFactoryFileError(SlimTestError):
    """A factory file failed to parse or validate."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"invalid factory file {path}: {detail}")
        self.path = path


def _safe_yaml() -> YAML:
    """A ruamel.yaml loader that produces plain dicts (no round-trip data)."""
    yaml = YAML(typ="safe")
    yaml.preserve_quotes = False
    return yaml


class FactoryRegistry:
    """Holds factories loaded from a directory tree, keyed by name.

    Use `FactoryRegistry.load(path)` for the normal entry point; the
    `__init__` is exposed mostly for tests that want to hand-build one.
    """

    def __init__(self, factories: Mapping[str, Factory] | None = None) -> None:
        self._factories: dict[str, Factory] = dict(factories or {})
        # Track defining file for nicer collision errors when load() is used.
        self._sources: dict[str, Path] = {}

    # -- public API -----------------------------------------------------

    @classmethod
    def load(cls, root: Path) -> FactoryRegistry:
        """Load every `*.yml` / `*.yaml` under `root` into a fresh registry.

        Subdirectories are walked recursively. A missing or empty `root`
        produces an empty registry rather than an error -- a project
        without factories is valid.
        """
        registry = cls()
        if not root.exists():
            return registry
        files = sorted(_iter_yaml_files(root))
        for path in files:
            registry._load_file(path)
        return registry

    @property
    def names(self) -> list[str]:
        """All known factory names, sorted."""
        return sorted(self._factories)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._factories

    def __len__(self) -> int:
        return len(self._factories)

    def get(self, name: str) -> Factory:
        """Return the factory by name or raise `UnknownFactoryError`."""
        try:
            return self._factories[name]
        except KeyError as exc:
            raise UnknownFactoryError(name, self._factories.keys()) from exc

    def resolve(
        self,
        factory_name: str,
        trait_name: str | None = None,
        override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a final row by merging base -> trait -> override.

        Each layer is applied with `deep_merge`. Unknown factory or trait
        names raise. Passing `override=None` is equivalent to `override={}`.
        """
        factory = self.get(factory_name)
        result: dict[str, Any] = dict(factory.base)
        if trait_name is not None:
            if trait_name not in factory.traits:
                raise UnknownTraitError(factory_name, trait_name, factory.traits.keys())
            result = deep_merge(result, factory.traits[trait_name])
        if override:
            result = deep_merge(result, override)
        return result

    # -- internals ------------------------------------------------------

    def _load_file(self, path: Path) -> None:
        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = _safe_yaml().load(fh)
        except Exception as exc:  # noqa: BLE001 -- ruamel raises broadly
            raise InvalidFactoryFileError(path, str(exc)) from exc

        if raw is None:
            # empty file -- treat as empty registry contribution
            return
        if not isinstance(raw, dict):
            raise InvalidFactoryFileError(
                path, f"expected a mapping at top level, got {type(raw).__name__}"
            )

        try:
            parsed = FactoryFile.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 -- pydantic ValidationError
            raise InvalidFactoryFileError(path, str(exc)) from exc

        for name, factory in parsed.factories.items():
            if name in self._factories:
                raise DuplicateFactoryError(
                    name=name,
                    first=self._sources[name],
                    second=path,
                )
            self._factories[name] = factory
            self._sources[name] = path


def _iter_yaml_files(root: Path) -> Iterable[Path]:
    """All `*.yml` / `*.yaml` under `root`, recursively."""
    for suffix in ("*.yml", "*.yaml"):
        yield from root.rglob(suffix)


__all__ = [
    "DuplicateFactoryError",
    "FactoryRegistry",
    "InvalidFactoryFileError",
    "SlimTestError",
    "UnknownFactoryError",
    "UnknownTraitError",
]
