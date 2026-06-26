"""Merge a named scenario's `given:` rows into a unit test.

Scenarios live under `meta.slimtest.scenarios.<name>` and exist to keep
common upstream setup out of individual tests. Merge rule:

  * per upstream key, the **test wins** -- if the test mentions
    upstream X, the test's rows are used verbatim and the scenario's
    rows for X are ignored;
  * upstreams the test doesn't mention but the scenario does are added
    from the scenario.

The result is a `UnitTestSpec` with the scenario name cleared and a
fully populated `given:`.
"""

from __future__ import annotations

from typing import Any

from .factory import SlimTestError
from .schema import ScenarioSpec, UnitTestSpec


class UnknownScenarioError(SlimTestError):
    """A test referenced a `scenario:` name that wasn't defined."""

    def __init__(self, name: str, known: list[str]) -> None:
        super().__init__(f"unknown scenario {name!r}; known scenarios: {sorted(known)}")
        self.name = name


def apply_scenario(
    spec: UnitTestSpec, scenarios: dict[str, ScenarioSpec]
) -> UnitTestSpec:
    """Resolve `spec.scenario` against `scenarios` and merge its `given:`.

    If `spec.scenario is None`, returns the spec unchanged. Unknown
    scenario names raise `UnknownScenarioError`.
    """
    if spec.scenario is None:
        return spec

    scenario = scenarios.get(spec.scenario)
    if scenario is None:
        raise UnknownScenarioError(spec.scenario, list(scenarios))

    merged_given: dict[str, list[dict[str, Any]]] = {**scenario.given}
    merged_given.update(spec.given)  # test wins per upstream key

    return UnitTestSpec(
        name=spec.name,
        description=spec.description,
        given=merged_given,
        expect=spec.expect,
        scenario=None,
        parametrize=spec.parametrize,
    )


__all__ = ["UnknownScenarioError", "apply_scenario"]
