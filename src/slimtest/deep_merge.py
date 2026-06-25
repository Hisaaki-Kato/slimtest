"""Deep merge for nested dicts.

Semantics (matches design.md §6.4):

* Nested dicts are merged recursively.
* Anything non-dict at a leaf overwrites: scalars, lists, and `None`
  included. Lists are NOT merged element-wise.
* Explicit `None` in `override` overwrites the base value (it is NOT
  treated as "delete").
"""

from __future__ import annotations

from typing import Any


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict that is `override` deep-merged on top of `base`.

    Neither `base` nor `override` is mutated. Keys present only in one side
    are kept as-is. For keys present in both, the dict-vs-dict case
    recurses; all other cases let the override value win.
    """
    result: dict[str, Any] = dict(base)
    for key, override_value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            result[key] = deep_merge(base_value, override_value)
        else:
            result[key] = override_value
    return result


__all__ = ["deep_merge"]
