"""Expand a parametrized `UnitTestSpec` into N concrete specs.

A parametrized test carries `parametrize: ParametrizeBlock` plus
`given:` / `expect:` blocks that act as templates: any string of the
exact form `"$<column>"` is replaced verbatim by that case's value for
`<column>`. Other strings (including ones that contain `$` mid-string)
pass through unchanged -- substitution is identifier-based, not Jinja.

Naming: each expanded test is named `<base>__<case_id>` where the
case_id comes from (in order):

  1. an explicit `id` column in the case row, if present;
  2. the case's first column value when it's a string;
  3. the integer index otherwise.

Special characters in derived IDs are normalised so the resulting name
stays a valid dbt unit-test identifier.
"""

from __future__ import annotations

import re
from typing import Any

from .factory import SlimTestError
from .schema import ParametrizeBlock, UnitTestSpec

_VAR_RE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")
_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9]+")


class InvalidParametrizeError(SlimTestError):
    """`parametrize:` block referenced a column that wasn't in the case row."""


def expand_parametrize(spec: UnitTestSpec) -> list[UnitTestSpec]:
    """Return N specs, one per case. If `spec.parametrize is None`, returns `[spec]`."""
    if spec.parametrize is None:
        return [spec]

    parametrize = spec.parametrize
    case_dicts = parametrize.as_dicts()
    if not case_dicts:
        return []

    expanded: list[UnitTestSpec] = []
    for index, case in enumerate(case_dicts):
        case_id = _case_id(case, parametrize, index)
        given = _substitute(spec.given, case)
        expect = _substitute(spec.expect, case)
        expanded.append(
            UnitTestSpec(
                name=f"{spec.name}__{case_id}",
                description=spec.description,
                given=given,
                expect=expect,
                scenario=spec.scenario,
                parametrize=None,
            )
        )
    return expanded


# -- internals ------------------------------------------------------


def _substitute(value: Any, case: dict[str, Any]) -> Any:
    """Replace `"$col"` occurrences anywhere inside `value` with `case[col]`."""
    if isinstance(value, str):
        match = _VAR_RE.fullmatch(value)
        if match is None:
            return value
        var_name = match.group(1)
        if var_name not in case:
            raise InvalidParametrizeError(
                f"parametrize template references ${var_name!s} but no such "
                f"column in case (have: {sorted(case)})"
            )
        return case[var_name]
    if isinstance(value, dict):
        return {k: _substitute(v, case) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, case) for v in value]
    return value


def _case_id(case: dict[str, Any], parametrize: ParametrizeBlock, index: int) -> str:
    """Derive a case identifier suitable for a test-name suffix."""
    explicit = case.get("id")
    if isinstance(explicit, str) and explicit:
        return _safe_id(explicit)

    first_col = _first_column(parametrize, case)
    if first_col is not None:
        first_val = case.get(first_col)
        if isinstance(first_val, str) and first_val:
            return _safe_id(first_val)

    return str(index)


def _first_column(parametrize: ParametrizeBlock, case: dict[str, Any]) -> str | None:
    if parametrize.columns:
        return parametrize.columns[0]
    if case:
        return next(iter(case))
    return None


def _safe_id(value: str) -> str:
    """Normalise a string into something safe to embed in a dbt test name."""
    cleaned = _ID_SAFE_RE.sub("_", value).strip("_")
    return cleaned or "_"


__all__ = [
    "InvalidParametrizeError",
    "expand_parametrize",
]
