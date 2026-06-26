"""Tests for `slimtest.scenario`."""

from __future__ import annotations

import pytest

from slimtest.scenario import UnknownScenarioError, apply_scenario
from slimtest.schema import ScenarioSpec, UnitTestSpec


def _spec(*, given=None, scenario=None):
    return UnitTestSpec(
        name="t",
        given=given or {},
        expect=[],
        scenario=scenario,
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


class TestUnknownScenario:
    def test_raises(self):
        with pytest.raises(UnknownScenarioError) as exc_info:
            apply_scenario(_spec(scenario="missing"), {"other": ScenarioSpec()})
        assert exc_info.value.name == "missing"
        assert "other" in str(exc_info.value)
