"""Resolve the supported subset of dbt's ``--select`` syntax.

The supported set operators match dbt's precedence: whitespace is a union
(OR), while commas are an intersection (AND). A selector term can identify
the model, the source test name, or either the source or concrete generated
test name. ``test_type:unit`` is the one supported method selector.

Selection happens in more than one phase of compilation. Parsed tests carry
their source name directly, while expanded tests may need a base name supplied
by the caller. ``SelectionIdentity`` keeps that distinction explicit so
parametrized names are never guessed by splitting an identifier.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from .expand import ExpandedUnitTest, make_prefixed_name
from .factory import SlimTestError
from .model_parser import ParsedUnitTest

_T = TypeVar("_T")
_SUPPORTED_METHOD = "test_type:unit"
_UNSUPPORTED_SELECTOR_CHARS = frozenset("+@*?[]")


class InvalidSelectorError(SlimTestError):
    """The selector uses syntax outside slimtest's supported subset."""


class NoMatchingTestsError(SlimTestError):
    """A non-empty, valid selector did not select any tests."""


@dataclass(frozen=True)
class SelectionIdentity:
    """Names used when matching one parsed or expanded test.

    ``base_name`` is the source test name before parametrization. For an
    unexpanded test it is the same as ``test_name``. ``test_name`` is the
    concrete source name (and therefore includes a parametrization suffix when
    the test has already been expanded), while ``prefixed_name`` is the exact
    generated dbt test identifier.
    """

    model_name: str
    base_name: str
    test_name: str
    prefixed_name: str


SelectableTest = ParsedUnitTest | ExpandedUnitTest
IdentityFn = Callable[[_T], SelectionIdentity]


def parse_selector(selector: str | None) -> list[list[str]]:
    """Parse a selector into OR groups containing AND terms.

    For example, ``"orders, test_type:unit customers"`` becomes
    ``[["orders", "test_type:unit"], ["customers"]]``. ``None`` and a
    whitespace-only value are intentionally represented by an empty list so
    callers can preserve the historical pass-through behavior.
    """
    if selector is None or not selector.strip():
        return []

    normalized = re.sub(r"\s*,\s*", ",", selector.strip())
    if normalized.startswith(",") or normalized.endswith(",") or ",," in normalized:
        raise InvalidSelectorError(
            f"invalid selector {selector!r}: commas must separate non-empty terms; "
            "empty terms are not supported"
        )

    groups: list[list[str]] = []
    for raw_group in re.split(r"\s+", normalized):
        terms = raw_group.split(",")
        for term in terms:
            _validate_term(term, selector)
        groups.append(terms)
    return groups


def selection_identity(
    test: SelectableTest, *, base_name: str | None = None
) -> SelectionIdentity:
    """Return the default selector identity for a parsed or expanded test.

    Expanded parametrized tests should pass their source test name through
    ``base_name`` (or expose a ``base_name`` attribute in a future model). No
    attempt is made to infer it from a generated name.
    """
    if isinstance(test, ParsedUnitTest):
        model_name = test.model_name
        test_name = test.spec.name
        return SelectionIdentity(
            model_name=model_name,
            base_name=test_name,
            test_name=test_name,
            prefixed_name=make_prefixed_name(model_name, test_name),
        )

    model_name = test.model
    test_name = test.original_name
    resolved_base_name = base_name
    if resolved_base_name is None:
        candidate = getattr(test, "base_name", None)
        if isinstance(candidate, str):
            resolved_base_name = candidate
    if resolved_base_name is None:
        resolved_base_name = test_name
    return SelectionIdentity(
        model_name=model_name,
        base_name=resolved_base_name,
        test_name=test_name,
        prefixed_name=test.prefixed_name,
    )


def matches(
    test: SelectableTest,
    token: str,
    *,
    identity: SelectionIdentity | None = None,
    base_name: str | None = None,
) -> bool:
    """Return whether one selector term matches ``test``.

    ``identity`` is useful to callers that have already expanded a test and
    retained its source/base name. ``base_name`` is a small convenience for
    the same case and is ignored when an identity is supplied.
    """
    _validate_term(token, token)
    resolved = identity or selection_identity(test, base_name=base_name)
    return _matches_identity(resolved, token)


def filter_tests(
    tests: Sequence[_T],
    selector: str | None,
    *,
    identity: IdentityFn[_T] | None = None,
) -> list[_T]:
    """Return tests selected by ``selector``.

    Terms separated by spaces are OR-ed. Terms separated by commas are
    AND-ed, so ``model,test_type:unit`` selects only that model. A caller
    selecting expanded tests can pass ``identity`` to preserve each test's
    original/base name. ``None`` and an empty selector remain pass-throughs.

    A non-empty selector that selects no tests raises ``NoMatchingTestsError``
    rather than silently compiling an empty result.
    """
    groups = parse_selector(selector)
    if not groups:
        return list(tests)

    identity_fn: IdentityFn[_T] = _default_identity if identity is None else identity

    selected: list[_T] = []
    for test in tests:
        resolved = identity_fn(test)
        if any(
            all(_matches_identity(resolved, token) for token in group)
            for group in groups
        ):
            selected.append(test)

    if not selected:
        raise NoMatchingTestsError(
            f"selector {selector!r} did not match any slimtest unit tests"
        )
    return selected


def _default_identity(test: _T) -> SelectionIdentity:
    if not isinstance(test, (ParsedUnitTest, ExpandedUnitTest)):
        raise TypeError(
            "filter_tests requires ParsedUnitTest or ExpandedUnitTest values "
            "unless an identity callback is supplied"
        )
    return selection_identity(test)


def _matches_identity(identity: SelectionIdentity, token: str) -> bool:
    if token == _SUPPORTED_METHOD:
        return True
    return token in {
        identity.model_name,
        identity.base_name,
        identity.test_name,
        identity.prefixed_name,
        make_prefixed_name(identity.model_name, identity.base_name),
    }


def _validate_term(term: str, selector: str) -> None:
    if not term:
        raise InvalidSelectorError(f"invalid selector {selector!r}: empty term")
    if any(char in term for char in _UNSUPPORTED_SELECTOR_CHARS):
        raise InvalidSelectorError(
            f"unsupported selector syntax {term!r}; graph operators and "
            "wildcards are not supported"
        )
    if ":" in term and term != _SUPPORTED_METHOD:
        raise InvalidSelectorError(
            f"unsupported selector method {term!r}; only test_type:unit is supported"
        )


__all__ = [
    "IdentityFn",
    "InvalidSelectorError",
    "NoMatchingTestsError",
    "SelectableTest",
    "SelectionIdentity",
    "filter_tests",
    "matches",
    "parse_selector",
    "selection_identity",
]
