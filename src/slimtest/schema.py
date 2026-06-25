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

from pydantic import BaseModel, ConfigDict, Field

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


class UnitTestSpec(BaseModel):
    """One entry under `models[*].meta.slimtest.unit_tests`.

    The `model:` field that dbt's standard unit_tests require is omitted;
    slimtest infers it from the enclosing `models[*].name`.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    given: dict[str, list[RawRow]]
    expect: list[RawRow]


class ModelSlimTest(BaseModel):
    """Content of `models[*].meta.slimtest` in a dbt model yml."""

    model_config = ConfigDict(extra="forbid")

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
    "SlimTestConfig",
    "ModelSlimTest",
    "RawRow",
    "UnitTestSpec",
]
