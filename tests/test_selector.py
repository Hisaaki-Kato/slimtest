"""Tests for `lighttest.selector`."""

from __future__ import annotations

from pathlib import Path

from lighttest.model_parser import ParsedUnitTest
from lighttest.schema import UnitTestSpec
from lighttest.selector import filter_tests, matches, parse_selector


def _spec(name: str) -> UnitTestSpec:
    return UnitTestSpec(name=name, given={"u": [{"x": 1}]}, expect=[])


def _parsed(model: str, test_name: str) -> ParsedUnitTest:
    return ParsedUnitTest(
        spec=_spec(test_name),
        model_name=model,
        source_path=Path("models/x.yml"),
        source_line=1,
    )


# -- parse_selector --------------------------------------------------


class TestParseSelector:
    def test_none_returns_empty(self):
        assert parse_selector(None) == []

    def test_empty_string_returns_empty(self):
        assert parse_selector("") == []

    def test_single_token(self):
        assert parse_selector("foo") == ["foo"]

    def test_comma_separated_tokens(self):
        assert parse_selector("a,b,c") == ["a", "b", "c"]

    def test_whitespace_is_stripped(self):
        assert parse_selector(" a , b ,  c ") == ["a", "b", "c"]

    def test_empty_tokens_are_dropped(self):
        assert parse_selector("a,,b") == ["a", "b"]


# -- matches ---------------------------------------------------------


class TestMatches:
    def test_test_type_unit_always_matches(self):
        assert matches(_parsed("m", "t"), "test_type:unit") is True

    def test_model_name_matches(self):
        assert matches(_parsed("orders", "t"), "orders") is True
        assert matches(_parsed("orders", "t"), "customers") is False

    def test_user_test_name_matches(self):
        assert matches(_parsed("orders", "happy_path"), "happy_path") is True

    def test_prefixed_name_matches(self):
        assert matches(_parsed("orders", "t"), "lighttest__orders__t") is True

    def test_unrelated_token_does_not_match(self):
        assert matches(_parsed("orders", "t"), "anything_else") is False


# -- filter_tests ----------------------------------------------------


class TestFilterTests:
    def test_none_selector_returns_input_unchanged(self):
        tests = [_parsed("m1", "t1"), _parsed("m2", "t2")]
        assert filter_tests(tests, None) == tests

    def test_empty_selector_returns_input_unchanged(self):
        tests = [_parsed("m1", "t1"), _parsed("m2", "t2")]
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
        result = filter_tests(tests, "lighttest__m2__b")
        assert [t.model_name for t in result] == ["m2"]

    def test_comma_separated_is_union(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b"), _parsed("m3", "c")]
        result = filter_tests(tests, "m1,m3")
        assert sorted(t.model_name for t in result) == ["m1", "m3"]

    def test_test_type_unit_returns_everything(self):
        tests = [_parsed("m1", "a"), _parsed("m2", "b")]
        assert filter_tests(tests, "test_type:unit") == tests
