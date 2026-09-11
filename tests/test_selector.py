"""Tests for ``slimtest.selector``."""

from __future__ import annotations

from pathlib import Path

import pytest

from slimtest.expand import ExpandedUnitTest, make_prefixed_name
from slimtest.factory import SlimTestError
from slimtest.model_parser import ParsedUnitTest
from slimtest.schema import OverridesSpec, UnitTestSpec
from slimtest.selector import (
    InvalidSelectorError,
    NoMatchingTestsError,
    filter_tests,
    matches,
    parse_selector,
    selection_identity,
)


def _spec(name: str) -> UnitTestSpec:
    return UnitTestSpec(name=name, given={"u": [{"x": 1}]}, expect=[])


def _parsed(model: str, test_name: str) -> ParsedUnitTest:
    return ParsedUnitTest(
        spec=_spec(test_name),
        model_name=model,
        source_path=Path("models/x.yml"),
        source_line=1,
    )


def _expanded(model: str, concrete_name: str) -> ExpandedUnitTest:
    return ExpandedUnitTest(
        original_name=concrete_name,
        prefixed_name=make_prefixed_name(model, concrete_name),
        model=model,
        description=None,
        given={"u": [{"x": 1}]},
        expect=[],
        overrides=OverridesSpec(),
        source_file=Path("models/x.yml"),
        source_line=1,
    )


def _expanded_identity(base_name: str):
    return lambda test: selection_identity(test, base_name=base_name)


# -- parse_selector --------------------------------------------------


class TestParseSelector:
    def test_none_and_empty_values_return_empty(self):
        assert parse_selector(None) == []
        assert parse_selector("") == []
        assert parse_selector("  \t") == []

    def test_single_token(self):
        assert parse_selector("foo") == [["foo"]]

    def test_comma_terms_are_an_and_group(self):
        assert parse_selector("a,b,c") == [["a", "b", "c"]]

    def test_whitespace_terms_are_or_groups(self):
        assert parse_selector(" a, b  c ") == [["a", "b"], ["c"]]

    @pytest.mark.parametrize("selector", [",a", "a,", "a,,b", "a, ,b"])
    def test_empty_comma_terms_are_rejected(self, selector: str):
        with pytest.raises(InvalidSelectorError, match="empty"):
            parse_selector(selector)


# -- matches ---------------------------------------------------------


class TestMatches:
    def test_test_type_unit_matches_supported_tests(self):
        assert matches(_parsed("m", "t"), "test_type:unit") is True

    def test_model_name_matches(self):
        assert matches(_parsed("orders", "t"), "orders") is True
        assert matches(_parsed("orders", "t"), "customers") is False

    def test_user_test_name_matches(self):
        assert matches(_parsed("orders", "happy_path"), "happy_path") is True

    def test_prefixed_name_matches(self):
        assert matches(_parsed("orders", "t"), "slimtest__orders__t") is True

    def test_unrelated_token_does_not_match(self):
        assert matches(_parsed("orders", "t"), "anything_else") is False

    @pytest.mark.parametrize("token", ["tag:foo", "path:models", "+orders", "orders*"])
    def test_unsupported_syntax_is_a_clear_error(self, token: str):
        with pytest.raises(SlimTestError, match="unsupported"):
            matches(_parsed("orders", "t"), token)


# -- filter_tests ----------------------------------------------------


class TestFilterTests:
    def test_none_and_empty_selectors_return_input_unchanged(self):
        tests = [_parsed("m1", "t1"), _parsed("m2", "t2")]
        assert filter_tests(tests, None) == tests
        assert filter_tests(tests, "") == tests

    def test_model_filter(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b"), _parsed("m1", "c")]
        result = filter_tests(tests, "m1")
        assert [t.spec.name for t in result] == ["a", "c"]

    def test_single_test_name_filter(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b")]
        result = filter_tests(tests, "b")
        assert len(result) == 1
        assert result[0].model_name == "m2"

    def test_prefixed_name_filter(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b")]
        result = filter_tests(tests, "slimtest__m2__b")
        assert [t.model_name for t in result] == ["m2"]

    def test_space_separated_terms_are_union(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b"), _parsed("m3", "c")]
        result = filter_tests(tests, "m1 m3")
        assert [t.model_name for t in result] == ["m1", "m3"]

    def test_comma_separated_terms_are_intersection(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b"), _parsed("m1", "c")]
        result = filter_tests(tests, "m1,test_type:unit")
        assert [t.model_name for t in result] == ["m1", "m1"]

    def test_test_type_unit_alone_returns_everything(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b")]
        assert filter_tests(tests, "test_type:unit") == tests

    def test_valid_selector_with_no_matches_raises(self):
        with pytest.raises(NoMatchingTestsError, match="did not match"):
            filter_tests([_parsed("m1", "a")], "missing")

    @pytest.mark.parametrize("selector", ["tag:foo", "model:m1", "+m1", "m1+", "m*"])
    def test_unsupported_selector_raises(self, selector: str):
        with pytest.raises(InvalidSelectorError, match="unsupported"):
            filter_tests([_parsed("m1", "a")], selector)

    def test_post_expansion_case_name_selects_exact_case(self):
        tests = [_expanded("m", "t__one"), _expanded("m", "t__two")]
        result = filter_tests(
            tests,
            "slimtest__m__t__two",
            identity=_expanded_identity("t"),
        )
        assert [test.original_name for test in result] == ["t__two"]

    @pytest.mark.parametrize("selector", ["t", "slimtest__m__t", "m"])
    def test_post_expansion_base_identity_selects_all_cases(self, selector: str):
        tests = [_expanded("m", "t__one"), _expanded("m", "t__two")]
        result = filter_tests(tests, selector, identity=_expanded_identity("t"))
        assert [test.original_name for test in result] == ["t__one", "t__two"]
