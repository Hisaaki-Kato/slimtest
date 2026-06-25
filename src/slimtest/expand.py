"""Turn a `UnitTestSpec` (with factory refs) into an `ExpandedUnitTest`.

Each row in `given.<upstream>` is either:

* a factory reference -- `{factory, trait?, override?}`
* a literal row dict   -- `{column_a: ..., column_b: ...}`

The discriminator is the presence of a `factory` key. Factory rows are
resolved against the registry; literal rows pass through unchanged.

`expect` rows are always literal (factories are not supported on the
expect side in the MVP; design.md §6.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .factory import FactoryRegistry, SlimTestError
from .schema import RawRow, UnitTestSpec

_FACTORY_ROW_KEYS = frozenset({"factory", "trait", "override"})


@dataclass(frozen=True)
class ExpandedUnitTest:
    """A unit test ready for emission as dbt-standard YAML.

    `prefixed_name` is what the generated yml emits and what dbt sees.
    `original_name` is what the user wrote (used in error messages).
    `auto_filled_upstreams` lists upstreams that the expansion layer
    injected itself (per design.md §6.5); used to emit warnings.
    """

    original_name: str
    prefixed_name: str
    model: str
    description: str | None
    given: dict[str, list[dict[str, Any]]]
    expect: list[dict[str, Any]]
    source_file: Path
    source_line: int
    auto_filled_upstreams: tuple[str, ...] = ()


class InvalidRowError(SlimTestError):
    """A row in `given.<upstream>` had unsupported shape (e.g. extra keys)."""


def make_prefixed_name(model: str, original_name: str) -> str:
    """Build the `slimtest__<model>__<name>` test identifier."""
    return f"slimtest__{model}__{original_name}"


def expand_unit_test(
    spec: UnitTestSpec,
    *,
    model: str,
    registry: FactoryRegistry,
    source_file: Path,
    source_line: int,
    expected_upstreams: list[str] | None = None,
    auto_fill: bool = False,
) -> ExpandedUnitTest:
    """Expand factory references in `spec.given`. `expect` is copied as-is.

    When `auto_fill=True` and `expected_upstreams` is given, any upstream
    that the model depends on but the user did NOT mention in `given`
    gets one `base`-row injected if a same-named factory exists. The
    upstreams that were filled this way are recorded on
    `ExpandedUnitTest.auto_filled_upstreams`.
    """
    expanded_given: dict[str, list[dict[str, Any]]] = {}
    for upstream, rows in spec.given.items():
        expanded_given[upstream] = [_expand_row(row, registry) for row in rows]

    auto_filled: list[str] = []
    if auto_fill and expected_upstreams:
        for upstream in expected_upstreams:
            if upstream in expanded_given:
                continue
            if upstream not in registry:
                continue
            expanded_given[upstream] = [registry.resolve(upstream)]
            auto_filled.append(upstream)

    return ExpandedUnitTest(
        original_name=spec.name,
        prefixed_name=make_prefixed_name(model, spec.name),
        model=model,
        description=spec.description,
        given=expanded_given,
        expect=[dict(row) for row in spec.expect],
        source_file=source_file,
        source_line=source_line,
        auto_filled_upstreams=tuple(auto_filled),
    )


def _expand_row(row: RawRow, registry: FactoryRegistry) -> dict[str, Any]:
    """Resolve one row -- factory ref or literal -- into a flat literal dict."""
    if "factory" not in row:
        return dict(row)

    extra_keys = set(row.keys()) - _FACTORY_ROW_KEYS
    if extra_keys:
        raise InvalidRowError(
            f"factory row has unknown keys {sorted(extra_keys)}; "
            f"expected only {sorted(_FACTORY_ROW_KEYS)}. "
            "To pass extra columns, put them under `override`."
        )

    factory_name = row["factory"]
    if not isinstance(factory_name, str):
        raise InvalidRowError(
            f"`factory` must be a string, got {type(factory_name).__name__}"
        )

    trait_name = row.get("trait")
    if trait_name is not None and not isinstance(trait_name, str):
        raise InvalidRowError(
            f"`trait` must be a string, got {type(trait_name).__name__}"
        )

    override = row.get("override") or {}
    if not isinstance(override, dict):
        raise InvalidRowError(
            f"`override` must be a mapping, got {type(override).__name__}"
        )

    return registry.resolve(factory_name, trait_name, override)


__all__ = [
    "ExpandedUnitTest",
    "InvalidRowError",
    "expand_unit_test",
    "make_prefixed_name",
]
