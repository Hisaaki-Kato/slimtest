"""Pydantic schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from slimtest.schema import (
    Factory,
    FactoryFile,
    ModelSlimTest,
    SlimTestConfig,
    UnitTestSpec,
)


class TestFactory:
    def test_base_only_is_valid(self):
        factory = Factory.model_validate({"base": {"id": 1}})
        assert factory.base == {"id": 1}
        assert factory.traits == {}

    def test_base_plus_traits_is_valid(self):
        factory = Factory.model_validate(
            {"base": {"id": 1}, "traits": {"premium": {"tier": "premium"}}}
        )
        assert factory.traits["premium"] == {"tier": "premium"}

    def test_missing_base_is_rejected(self):
        with pytest.raises(ValidationError):
            Factory.model_validate({"traits": {}})

    def test_extra_top_level_field_is_rejected(self):
        with pytest.raises(ValidationError):
            Factory.model_validate({"base": {}, "wat": 1})

    def test_traits_must_be_dict_of_dicts(self):
        with pytest.raises(ValidationError):
            Factory.model_validate({"base": {}, "traits": {"x": "not a dict"}})


class TestFactoryFile:
    def test_empty_factories_is_valid(self):
        file = FactoryFile.model_validate({"factories": {}})
        assert file.factories == {}

    def test_missing_factories_key_is_rejected(self):
        with pytest.raises(ValidationError):
            FactoryFile.model_validate({})

    def test_extra_top_level_field_is_rejected(self):
        with pytest.raises(ValidationError):
            FactoryFile.model_validate({"factories": {}, "other": 1})


class TestUnitTestSpec:
    def _minimal(self) -> dict[str, object]:
        return {
            "name": "test_x",
            "given": {"upstream": [{"factory": "f"}]},
            "expect": [{"col_a": 1}],
        }

    def test_minimal_spec_is_valid(self):
        spec = UnitTestSpec.model_validate(self._minimal())
        assert spec.name == "test_x"
        assert spec.description is None
        assert spec.given == {"upstream": [{"factory": "f"}]}

    def test_description_is_optional(self):
        spec = UnitTestSpec.model_validate({**self._minimal(), "description": "hi"})
        assert spec.description == "hi"

    def test_missing_name_is_rejected(self):
        spec = self._minimal()
        del spec["name"]
        with pytest.raises(ValidationError):
            UnitTestSpec.model_validate(spec)

    def test_extra_top_level_field_is_rejected(self):
        with pytest.raises(ValidationError):
            UnitTestSpec.model_validate({**self._minimal(), "unknown": 1})


class TestModelSlimTest:
    def test_no_unit_tests_defaults_to_empty_list(self):
        block = ModelSlimTest.model_validate({})
        assert block.unit_tests == []

    def test_unit_tests_list_is_parsed(self):
        block = ModelSlimTest.model_validate(
            {
                "unit_tests": [
                    {
                        "name": "t1",
                        "given": {"u": [{"factory": "f"}]},
                        "expect": [{"a": 1}],
                    }
                ]
            }
        )
        assert len(block.unit_tests) == 1
        assert block.unit_tests[0].name == "t1"


class TestSlimTestConfig:
    def test_defaults(self):
        cfg = SlimTestConfig()
        assert cfg.factories_path == "tests/slimtest_factories"
        assert cfg.generated_yml_path == "target/slimtest"

    def test_overrides(self):
        cfg = SlimTestConfig.model_validate(
            {"factories_path": "tests/factories", "generated_yml_path": "tmp/lt"}
        )
        assert cfg.factories_path == "tests/factories"
        assert cfg.generated_yml_path == "tmp/lt"

    def test_extra_field_is_rejected(self):
        with pytest.raises(ValidationError):
            SlimTestConfig.model_validate({"unknown_key": True})


class TestScenarioSpec:
    def test_default_given_is_empty(self):
        from slimtest.schema import ScenarioSpec

        spec = ScenarioSpec()
        assert spec.given == {}

    def test_parses_given(self):
        from slimtest.schema import ScenarioSpec

        spec = ScenarioSpec.model_validate({"given": {"u": [{"x": 1}]}})
        assert spec.given == {"u": [{"x": 1}]}

    def test_extra_field_rejected(self):
        from slimtest.schema import ScenarioSpec

        with pytest.raises(ValidationError):
            ScenarioSpec.model_validate({"given": {}, "bogus": 1})


class TestParametrizeBlock:
    def test_list_of_dicts_form(self):
        from slimtest.schema import ParametrizeBlock

        block = ParametrizeBlock.model_validate(
            {"cases": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]}
        )
        assert block.as_dicts() == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

    def test_columns_plus_list_form(self):
        from slimtest.schema import ParametrizeBlock

        block = ParametrizeBlock.model_validate(
            {"columns": ["a", "b"], "cases": [[1, 2], [3, 4]]}
        )
        assert block.as_dicts() == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


class TestModelSlimTestWithScenarios:
    def test_scenarios_parse_alongside_unit_tests(self):
        from slimtest.schema import ModelSlimTest

        block = ModelSlimTest.model_validate(
            {
                "scenarios": {"s": {"given": {"u": [{"x": 1}]}}},
                "unit_tests": [
                    {
                        "name": "t",
                        "scenario": "s",
                        "given": {},
                        "expect": [],
                    }
                ],
            }
        )
        assert "s" in block.scenarios
        assert block.unit_tests[0].scenario == "s"
