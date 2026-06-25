"""`--select` resolution.

MVP scope (matches design.md §7.2 / §15.1):

  * bare model name                -> all tests for that model
  * bare test name (user-written)  -> tests with that `name:` field
  * prefixed name                  -> the single generated test
  * `test_type:unit`               -> no-op (lighttest is unit-tests only)
  * comma-separated tokens         -> union (OR)

Tag-based selection (`tag:foo`), graph operators (`+`, `@`), and path
prefixes are deferred to a later phase.
"""

from __future__ import annotations

from .expand import make_prefixed_name
from .model_parser import ParsedUnitTest


def parse_selector(selector: str | None) -> list[str]:
    """Split a raw `--select` string into individual tokens."""
    if not selector:
        return []
    return [tok.strip() for tok in selector.split(",") if tok.strip()]


def matches(test: ParsedUnitTest, token: str) -> bool:
    """True iff `token` selects `test` under MVP rules."""
    if token == "test_type:unit":
        return True
    if token == test.model_name:
        return True
    if token == test.spec.name:
        return True
    return token == make_prefixed_name(test.model_name, test.spec.name)


def filter_tests(
    tests: list[ParsedUnitTest], selector: str | None
) -> list[ParsedUnitTest]:
    """Return only those tests selected by `selector`.

    A `None` or empty selector is a pass-through (no filtering).
    """
    tokens = parse_selector(selector)
    if not tokens:
        return list(tests)
    return [t for t in tests if any(matches(t, tok) for tok in tokens)]


__all__ = ["filter_tests", "matches", "parse_selector"]
