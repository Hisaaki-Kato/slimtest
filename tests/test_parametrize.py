"""Tests for `slimtest.parametrize`."""

from __future__ import annotations

import pytest

from slimtest.parametrize import InvalidParametrizeError, expand_parametrize
from slimtest.schema import ParametrizeBlock, UnitTestSpec


def _spec(parametrize=None, given=None, expect=None, scenario=None, name="t"):
    return UnitTestSpec(
        name=name,
        given=given or {"u": [{"factory": "u"}]},
        expect=expect or [{"x": 1}],
        scenario=scenario,
        parametrize=parametrize,
    )


class TestNoParametrize:
    def test_returns_spec_unchanged(self):
        spec = _spec()
        result = expand_parametrize(spec)
        assert result == [spec]


class TestListOfDictsCases:
    def test_substitutes_into_given_and_expect(self):
        spec = _spec(
            parametrize=ParametrizeBlock(
                cases=[
                    {"trait": "placed", "status": "pending"},
                    {"trait": "paid", "status": "processing"},
                ]
            ),
            given={
                "events": [
                    {"factory": "events", "trait": "$trait", "override": {"id": 1}}
                ]
            },
            expect=[{"status": "$status"}],
        )
        expanded = expand_parametrize(spec)
        assert len(expanded) == 2
        assert expanded[0].given == {
            "events": [{"factory": "events", "trait": "placed", "override": {"id": 1}}]
        }
        assert expanded[0].expect == [{"status": "pending"}]
        assert expanded[1].expect == [{"status": "processing"}]


class TestListOfListsCases:
    def test_requires_columns(self):
        with pytest.raises(ValueError, match="`columns:` must be provided"):
            ParametrizeBlock(cases=[["placed", "pending"], ["paid", "processing"]])

    def test_normalises_via_columns(self):
        block = ParametrizeBlock(
            columns=["trait", "status"],
            cases=[["placed", "pending"], ["paid", "processing"]],
        )
        assert block.as_dicts() == [
            {"trait": "placed", "status": "pending"},
            {"trait": "paid", "status": "processing"},
        ]

    def test_mismatched_case_width_rejected(self):
        with pytest.raises(ValueError, match="entries, expected"):
            ParametrizeBlock(
                columns=["a", "b", "c"],
                cases=[["1", "2"]],
            )

    def test_mixed_dict_and_list_cases_rejected(self):
        with pytest.raises(ValueError, match="all dicts or all lists"):
            ParametrizeBlock(
                cases=[{"a": 1}, ["a", "b"]],
            )


class TestSubstitutionRules:
    def test_only_full_string_dollar_refs_substituted(self):
        # `$trait` -> substituted. `prefix_$trait` is NOT (no embedded subst).
        spec = _spec(
            parametrize=ParametrizeBlock(cases=[{"trait": "placed"}]),
            given={"events": [{"event_type": "$trait", "label": "prefix_$trait"}]},
            expect=[],
        )
        expanded = expand_parametrize(spec)[0]
        assert expanded.given["events"][0]["event_type"] == "placed"
        # Embedded substitution intentionally NOT performed.
        assert expanded.given["events"][0]["label"] == "prefix_$trait"

    def test_substitutes_nested_dicts_and_lists(self):
        spec = _spec(
            parametrize=ParametrizeBlock(cases=[{"id": 42, "val": "x"}]),
            given={
                "u": [
                    {"override": {"id": "$id", "nested": {"v": "$val"}}},
                ]
            },
            expect=[{"col": "$val"}],
        )
        expanded = expand_parametrize(spec)[0]
        assert expanded.given == {"u": [{"override": {"id": 42, "nested": {"v": "x"}}}]}
        assert expanded.expect == [{"col": "x"}]

    def test_unknown_var_reference_raises(self):
        spec = _spec(
            parametrize=ParametrizeBlock(cases=[{"trait": "placed"}]),
            given={"u": [{"col": "$missing"}]},
            expect=[],
        )
        with pytest.raises(InvalidParametrizeError, match=r"\$missing"):
            expand_parametrize(spec)


class TestExpandedNaming:
    def test_uses_first_column_string_value(self):
        spec = _spec(
            name="event_maps",
            parametrize=ParametrizeBlock(
                columns=["trait", "status"],
                cases=[["placed", "pending"], ["paid", "processing"]],
            ),
            given={"u": []},
            expect=[],
        )
        names = [s.name for s in expand_parametrize(spec)]
        assert names == ["event_maps__placed", "event_maps__paid"]

    def test_explicit_id_overrides_first_column(self):
        spec = _spec(
            name="t",
            parametrize=ParametrizeBlock(
                cases=[
                    {"id": "case_one", "x": 1},
                    {"id": "case_two", "x": 2},
                ]
            ),
            given={"u": []},
            expect=[],
        )
        names = [s.name for s in expand_parametrize(spec)]
        assert names == ["t__case_one", "t__case_two"]

    def test_falls_back_to_index_when_no_string_id(self):
        spec = _spec(
            name="t",
            parametrize=ParametrizeBlock(
                columns=["n"],
                cases=[[1], [2]],
            ),
            given={"u": []},
            expect=[],
        )
        names = [s.name for s in expand_parametrize(spec)]
        assert names == ["t__0", "t__1"]

    def test_special_characters_are_normalised(self):
        spec = _spec(
            name="t",
            parametrize=ParametrizeBlock(
                cases=[{"id": "with spaces and-dashes!"}],
            ),
            given={"u": []},
            expect=[],
        )
        assert expand_parametrize(spec)[0].name == "t__with_spaces_and_dashes"


class TestParametrizeWithScenarioPreserved:
    def test_scenario_reference_carries_to_each_case(self):
        spec = _spec(
            scenario="my_scenario",
            parametrize=ParametrizeBlock(
                cases=[{"trait": "placed"}, {"trait": "paid"}]
            ),
        )
        expanded = expand_parametrize(spec)
        assert all(s.scenario == "my_scenario" for s in expanded)
        assert all(s.parametrize is None for s in expanded)


class TestEmptyCases:
    def test_no_cases_returns_empty_list(self):
        spec = _spec(parametrize=ParametrizeBlock(cases=[]))
        assert expand_parametrize(spec) == []
