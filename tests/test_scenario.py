"""Tests for `slimtest.scenario`."""

from __future__ import annotations

import pytest

from slimtest.scenario import UnknownScenarioError, apply_scenario
from slimtest.schema import OverridesSpec, ScenarioSpec, UnitTestSpec


def _spec(*, given=None, scenario=None, overrides=None):
    return UnitTestSpec(
        name="t",
        given=given or {},
        expect=[],
        scenario=scenario,
        overrides=overrides or OverridesSpec(),
    )


class TestNoScenarioReference:
    def test_returns_spec_unchanged(self):
        spec = _spec(given={"u": [{"x": 1}]})
        assert apply_scenario(spec, {}) is spec


class TestScenarioMerge:
    def test_adds_upstreams_only_in_scenario(self):
        scenarios = {
            "s": ScenarioSpec(
                given={
                    "customers": [{"id": 1}],
                    "products": [{"id": 100}],
                }
            )
        }
        spec = _spec(scenario="s", given={"order_events": [{"id": 9}]})
        merged = apply_scenario(spec, scenarios)
        assert set(merged.given) == {"order_events", "customers", "products"}
        assert merged.given["customers"] == [{"id": 1}]
        assert merged.given["products"] == [{"id": 100}]
        assert merged.given["order_events"] == [{"id": 9}]

    def test_test_wins_for_overlapping_upstream_key(self):
        scenarios = {"s": ScenarioSpec(given={"customers": [{"id": 1}]})}
        spec = _spec(scenario="s", given={"customers": [{"id": 999}]})
        merged = apply_scenario(spec, scenarios)
        # scenario's customers row is entirely replaced.
        assert merged.given["customers"] == [{"id": 999}]

    def test_scenario_cleared_after_merge(self):
        scenarios = {"s": ScenarioSpec(given={"u": [{"x": 1}]})}
        spec = _spec(scenario="s")
        merged = apply_scenario(spec, scenarios)
        assert merged.scenario is None

    def test_empty_scenario_given_is_noop_on_merge(self):
        scenarios = {"s": ScenarioSpec()}
        spec = _spec(scenario="s", given={"u": [{"x": 1}]})
        merged = apply_scenario(spec, scenarios)
        assert merged.given == {"u": [{"x": 1}]}

    def test_overrides_merge_per_key_with_test_winning(self):
        defaults = OverridesSpec(
            macros={"shared": "global", "global_only": 1},
            vars={"region": "global"},
            env_vars={"GLOBAL": "yes"},
        )
        scenarios = {
            "s": ScenarioSpec(
                overrides=OverridesSpec(
                    macros={"shared": "scenario", "scenario_only": 2},
                    vars={"region": "scenario"},
                )
            )
        }
        spec = _spec(
            scenario="s",
            overrides=OverridesSpec(
                macros={"shared": "test"},
                env_vars={"TEST": "yes"},
            ),
        )

        merged = apply_scenario(
            spec,
            scenarios,
            default_overrides=defaults,
        )

        assert merged.overrides.macros == {
            "shared": "test",
            "global_only": 1,
            "scenario_only": 2,
        }
        assert merged.overrides.vars == {"region": "scenario"}
        assert merged.overrides.env_vars == {"GLOBAL": "yes", "TEST": "yes"}

    def test_global_overrides_apply_without_scenario(self):
        spec = _spec(overrides=OverridesSpec(vars={"shared": "test"}))
        merged = apply_scenario(
            spec,
            {},
            default_overrides=OverridesSpec(
                vars={"shared": "global", "global_only": True}
            ),
        )
        assert merged.overrides.vars == {"shared": "test", "global_only": True}


class TestUnknownScenario:
    def test_raises(self):
        with pytest.raises(UnknownScenarioError) as exc_info:
            apply_scenario(_spec(scenario="missing"), {"other": ScenarioSpec()})
        assert exc_info.value.name == "missing"
        assert "other" in str(exc_info.value)
