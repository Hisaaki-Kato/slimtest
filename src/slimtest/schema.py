"""Pydantic schemas for slimtest user inputs.

These cover the shapes a user writes by hand:

* `tests/slimtest_factories/*.yml`  -> `FactoryFile`
* `models/**/*.yml` (the `meta.slimtest` block) -> `ModelSlimTest`
* `slimtest.yml`                    -> `SlimTestConfig`

Row contents (both `given.<upstream>` rows and `expect` rows) are kept as
raw `dict[str, Any]` here. They mix two shapes (factory reference vs.
literal upstream row) and the keys come from arbitrary upstream columns,
so strict pydantic validation does not buy us much. The expansion layer
in `slimtest.factory` and `slimtest.compile` interprets them.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# A raw row as written by the user. Either:
#   {factory: <name>, trait?: <name>, override?: {...}}     -- factory ref
#   {<column>: <value>, ...}                                -- literal row
RawRow = dict[str, Any]


class Factory(BaseModel):
    """One factory definition: a base row plus optional named traits.

    `base` is the common payload every row built from this factory starts
    from. `traits` are named diffs that get deep-merged on top of `base`
    before the test-case-level override is applied.
    """

    model_config = ConfigDict(extra="forbid")

    base: dict[str, Any]
    traits: dict[str, dict[str, Any]] = Field(default_factory=dict)


class FactoryFile(BaseModel):
    """Top-level shape of a single file under `tests/slimtest_factories/`."""

    model_config = ConfigDict(extra="forbid")

    factories: dict[str, Factory]


class ScenarioSpec(BaseModel):
    """A named bundle of `given:` rows reusable across tests.

    Lives under `meta.slimtest.scenarios.<name>`. A test references it by
    name (`scenario: <name>`); the compile layer merges this block's
    `given` into the test's `given` (per-upstream test-wins replacement).
    """

    model_config = ConfigDict(extra="forbid")

    given: dict[str, list[RawRow]] = Field(default_factory=dict)


class ParametrizeBlock(BaseModel):
    """Tabular case table that expands one UnitTestSpec into N tests.

    Two equivalent input shapes are supported:

    * `cases:` as list of lists, paired with `columns:` (header row):
        columns: [trait, expected_status]
        cases:
          - [placed, pending]
          - [paid,   processing]

    * `cases:` as list of dicts (header is implicit in the dict keys):
        cases:
          - {trait: placed, expected_status: pending}
          - {trait: paid,   expected_status: processing}

    Each case becomes a separate test; values are substituted into the
    enclosing test's `given:` / `expect:` wherever `$<column>` appears.
    """

    model_config = ConfigDict(extra="forbid")

    columns: list[str] | None = None
    cases: list[Any] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalise(self) -> ParametrizeBlock:
        if not self.cases:
            return self
        first = self.cases[0]
        if isinstance(first, dict):
            if not all(isinstance(c, dict) for c in self.cases):
                raise ValueError("parametrize.cases must be all dicts or all lists")
            return self
        if not all(isinstance(c, list) for c in self.cases):
            raise ValueError("parametrize.cases must be all dicts or all lists")
        if self.columns is None:
            raise ValueError(
                "parametrize.cases is a list of lists; `columns:` must be provided"
            )
        bad = [i for i, c in enumerate(self.cases) if len(c) != len(self.columns)]
        if bad:
            raise ValueError(
                f"parametrize.cases[{bad[0]}] has {len(self.cases[bad[0]])} entries, "
                f"expected {len(self.columns)} to match columns {self.columns}"
            )
        return self

    def as_dicts(self) -> list[dict[str, Any]]:
        """Normalise both shapes to a uniform `list[dict[col, value]]`."""
        if not self.cases:
            return []
        if isinstance(self.cases[0], dict):
            return [dict(c) for c in self.cases]
        assert self.columns is not None
        return [dict(zip(self.columns, c, strict=True)) for c in self.cases]


class UnitTestSpec(BaseModel):
    """One entry under `models[*].meta.slimtest.unit_tests`.

    The `model:` field that dbt's standard unit_tests require is omitted;
    slimtest infers it from the enclosing `models[*].name`.

    `scenario` (optional) references a `meta.slimtest.scenarios.<name>`
    block whose `given:` is merged into this test's `given:` before
    factory expansion (test-wins per-upstream-key).

    `parametrize` (optional) turns this single spec into N expanded
    tests; values are substituted into `given:`/`expect:` wherever
    `$<column>` appears verbatim.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    given: dict[str, list[RawRow]] = Field(default_factory=dict)
    expect: list[RawRow] = Field(default_factory=list)
    scenario: str | None = None
    parametrize: ParametrizeBlock | None = None


class ModelSlimTest(BaseModel):
    """Content of `models[*].meta.slimtest` in a dbt model yml."""

    model_config = ConfigDict(extra="forbid")

    scenarios: dict[str, ScenarioSpec] = Field(default_factory=dict)
    unit_tests: list[UnitTestSpec] = Field(default_factory=list)


class SlimTestConfig(BaseModel):
    """`slimtest.yml` -- minimal MVP shape.

    Paths are relative to the dbt project root.

    `auto_fill_upstreams` toggles the "if a model depends on an upstream
    that wasn't mentioned in `given` AND a same-named factory exists,
    inject the factory's base row as one row of that upstream" behaviour
    described in design.md §6.5. Default on; set to false to opt out.
    """

    model_config = ConfigDict(extra="forbid")

    factories_path: str = "tests/slimtest_factories"
    generated_yml_path: str = "target/slimtest"
    auto_fill_upstreams: bool = True


__all__ = [
    "Factory",
    "FactoryFile",
    "ModelSlimTest",
    "ParametrizeBlock",
    "RawRow",
    "ScenarioSpec",
    "SlimTestConfig",
    "UnitTestSpec",
]
