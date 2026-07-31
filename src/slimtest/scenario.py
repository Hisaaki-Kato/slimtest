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
from .schema import OverridesSpec, ScenarioSpec, UnitTestSpec


class UnknownScenarioError(SlimTestError):
    """A test referenced a `scenario:` name that wasn't defined."""

    def __init__(self, name: str, known: list[str]) -> None:
        super().__init__(f"unknown scenario {name!r}; known scenarios: {sorted(known)}")
        self.name = name


def apply_scenario(
    spec: UnitTestSpec,
    scenarios: dict[str, ScenarioSpec],
    *,
    default_overrides: OverridesSpec | None = None,
) -> UnitTestSpec:
    """Resolve a scenario and merge config/scenario/test overrides.

    `default_overrides` contains the already-merged project and model layers.
    Overall precedence is project < model < scenario < test, merged per key
    within `macros`, `vars`, and `env_vars`. If there is no scenario and no
    default override, returns the spec unchanged. Unknown scenario names raise
    `UnknownScenarioError`.
    """
    if spec.scenario is None and (
        default_overrides is None or default_overrides.is_empty
    ):
        return spec

    scenario: ScenarioSpec | None = None
    if spec.scenario is not None:
        scenario = scenarios.get(spec.scenario)
        if scenario is None:
            raise UnknownScenarioError(spec.scenario, list(scenarios))

    merged_given: dict[str, list[dict[str, Any]]] = {
        **(scenario.given if scenario is not None else {})
    }
    merged_given.update(spec.given)  # test wins per upstream key
    merged_overrides = merge_overrides(
        default_overrides,
        scenario.overrides if scenario is not None else None,
        spec.overrides,
    )

    return UnitTestSpec(
        name=spec.name,
        description=spec.description,
        given=merged_given,
        expect=spec.expect,
        scenario=None,
        parametrize=spec.parametrize,
        overrides=merged_overrides,
    )


def merge_overrides(*layers: OverridesSpec | None) -> OverridesSpec:
    """Merge override layers per section and key, with later layers winning."""
    macros: dict[str, Any] = {}
    vars_: dict[str, Any] = {}
    env_vars: dict[str, Any] = {}
    for layer in layers:
        if layer is None:
            continue
        macros.update(layer.macros)
        vars_.update(layer.vars)
        env_vars.update(layer.env_vars)
    return OverridesSpec(macros=macros, vars=vars_, env_vars=env_vars)


__all__ = ["UnknownScenarioError", "apply_scenario", "merge_overrides"]
