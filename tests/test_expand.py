"""Tests for `slimtest.expand`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from slimtest.expand import (
    InvalidRowError,
    expand_unit_test,
    make_prefixed_name,
)
from slimtest.factory import FactoryRegistry, UnknownFactoryError
from slimtest.schema import Factory, UnitTestSpec


def _make_spec(
    *,
    given: dict[str, list[dict[str, Any]]] | None = None,
    expect: list[dict[str, Any]] | None = None,
    name: str = "test_x",
    description: str | None = None,
) -> UnitTestSpec:
    # Distinguish None ("use default") from {} ("explicitly empty").
    resolved_given = given if given is not None else {"upstream": [{"factory": "u"}]}
    resolved_expect = expect if expect is not None else [{"col": 1}]
    return UnitTestSpec(
        name=name,
        description=description,
        given=resolved_given,
        expect=resolved_expect,
    )


def _registry(**factories: Factory) -> FactoryRegistry:
    return FactoryRegistry(factories)


SRC = Path("models/x.yml")


class TestPrefixedName:
    def test_format(self):
        assert make_prefixed_name("hoge", "test_xxx") == "slimtest__hoge__test_xxx"

    def test_preserves_underscores_in_name(self):
        assert make_prefixed_name("a_b", "c_d") == "slimtest__a_b__c_d"


class TestRowExpansion:
    def test_literal_row_passes_through(self):
        spec = _make_spec(given={"u": [{"a": 1, "b": "x"}]})
        result = expand_unit_test(
            spec,
            model="m",
            registry=_registry(),
            source_file=SRC,
            source_line=10,
        )
        assert result.given == {"u": [{"a": 1, "b": "x"}]}

    def test_factory_row_with_base_only(self):
        registry = _registry(user=Factory(base={"id": 1, "name": "x"}))
        spec = _make_spec(given={"u": [{"factory": "user"}]})
        result = expand_unit_test(
            spec, model="m", registry=registry, source_file=SRC, source_line=10
        )
        assert result.given == {"u": [{"id": 1, "name": "x"}]}

    def test_factory_row_with_trait(self):
        registry = _registry(
            user=Factory(
                base={"id": 1, "tier": "std"},
                traits={"premium": {"tier": "premium"}},
            )
        )
        spec = _make_spec(given={"u": [{"factory": "user", "trait": "premium"}]})
        result = expand_unit_test(
            spec, model="m", registry=registry, source_file=SRC, source_line=10
        )
        assert result.given == {"u": [{"id": 1, "tier": "premium"}]}

    def test_factory_row_with_override(self):
        registry = _registry(user=Factory(base={"id": 1, "name": "x"}))
        spec = _make_spec(
            given={"u": [{"factory": "user", "override": {"id": 99}}]},
        )
        result = expand_unit_test(
            spec, model="m", registry=registry, source_file=SRC, source_line=10
        )
        assert result.given == {"u": [{"id": 99, "name": "x"}]}

    def test_factory_row_with_trait_and_override(self):
        registry = _registry(
            user=Factory(
                base={"id": 1, "tier": "std", "country": "JP"},
                traits={"premium": {"tier": "premium"}},
            )
        )
        spec = _make_spec(
            given={
                "u": [
                    {
                        "factory": "user",
                        "trait": "premium",
                        "override": {"country": "US"},
                    }
                ]
            },
        )
        result = expand_unit_test(
            spec, model="m", registry=registry, source_file=SRC, source_line=10
        )
        assert result.given == {"u": [{"id": 1, "tier": "premium", "country": "US"}]}

    def test_mixed_factory_and_literal_rows(self):
        registry = _registry(user=Factory(base={"id": 1}))
        spec = _make_spec(
            given={
                "u": [
                    {"factory": "user"},
                    {"id": 99, "explicit_col": True},
                ]
            },
        )
        result = expand_unit_test(
            spec, model="m", registry=registry, source_file=SRC, source_line=10
        )
        assert result.given == {
            "u": [
                {"id": 1},
                {"id": 99, "explicit_col": True},
            ]
        }

    def test_unknown_factory_raises(self):
        spec = _make_spec(given={"u": [{"factory": "missing"}]})
        with pytest.raises(UnknownFactoryError):
            expand_unit_test(
                spec,
                model="m",
                registry=_registry(),
                source_file=SRC,
                source_line=10,
            )


class TestRowValidation:
    def test_factory_row_with_unknown_keys_raises(self):
        registry = _registry(user=Factory(base={}))
        spec = _make_spec(given={"u": [{"factory": "user", "bogus_key": 1}]})
        with pytest.raises(InvalidRowError, match="unknown keys"):
            expand_unit_test(
                spec,
                model="m",
                registry=registry,
                source_file=SRC,
                source_line=10,
            )

    def test_factory_name_must_be_string(self):
        spec = _make_spec(given={"u": [{"factory": 42}]})
        with pytest.raises(InvalidRowError, match="`factory` must be a string"):
            expand_unit_test(
                spec,
                model="m",
                registry=_registry(),
                source_file=SRC,
                source_line=10,
            )

    def test_trait_must_be_string(self):
        registry = _registry(user=Factory(base={}, traits={"a": {}}))
        spec = _make_spec(given={"u": [{"factory": "user", "trait": 5}]})
        with pytest.raises(InvalidRowError, match="`trait` must be a string"):
            expand_unit_test(
                spec,
                model="m",
                registry=registry,
                source_file=SRC,
                source_line=10,
            )

    def test_override_must_be_mapping(self):
        registry = _registry(user=Factory(base={}))
        spec = _make_spec(given={"u": [{"factory": "user", "override": [1, 2]}]})
        with pytest.raises(InvalidRowError, match="`override` must be a mapping"):
            expand_unit_test(
                spec,
                model="m",
                registry=registry,
                source_file=SRC,
                source_line=10,
            )


class TestExpandedFields:
    def test_metadata_is_preserved(self):
        registry = _registry(u=Factory(base={"x": 1}))
        spec = _make_spec(
            name="test_xxx", description="docs", given={"upstream": [{"factory": "u"}]}
        )
        result = expand_unit_test(
            spec,
            model="my_model",
            registry=registry,
            source_file=Path("models/my_model.yml"),
            source_line=42,
        )
        assert result.original_name == "test_xxx"
        assert result.prefixed_name == "slimtest__my_model__test_xxx"
        assert result.model == "my_model"
        assert result.description == "docs"
        assert result.source_file == Path("models/my_model.yml")
        assert result.source_line == 42

    def test_expect_is_passed_through_with_defensive_copy(self):
        registry = _registry()
        original_expect = [{"col": 1}]
        spec = _make_spec(given={"u": []}, expect=original_expect)
        result = expand_unit_test(
            spec, model="m", registry=registry, source_file=SRC, source_line=10
        )
        assert result.expect == [{"col": 1}]
        # Mutating the source must not change the expanded result.
        original_expect[0]["col"] = 999
        assert result.expect[0]["col"] == 1


# -- upstream auto-fill ---------------------------------------------


class TestAutoFillUpstreams:
    def test_disabled_by_default(self):
        # auto_fill=False -> no injection even when expected_upstreams given.
        registry = _registry(users=Factory(base={"id": 1}))
        spec = _make_spec(given={"orders": [{"x": 1}]})
        result = expand_unit_test(
            spec,
            model="m",
            registry=registry,
            source_file=SRC,
            source_line=1,
            expected_upstreams=["users", "orders"],
            auto_fill=False,
        )
        assert set(result.given.keys()) == {"orders"}
        assert result.auto_filled_upstreams == ()

    def test_injects_factory_base_when_upstream_unmentioned(self):
        registry = _registry(users=Factory(base={"id": 1, "name": "alice"}))
        spec = _make_spec(given={"orders": [{"x": 1}]})
        result = expand_unit_test(
            spec,
            model="m",
            registry=registry,
            source_file=SRC,
            source_line=1,
            expected_upstreams=["users", "orders"],
            auto_fill=True,
        )
        assert result.given == {
            "orders": [{"x": 1}],
            "users": [{"id": 1, "name": "alice"}],
        }
        assert result.auto_filled_upstreams == ("users",)

    def test_does_not_inject_when_user_supplied_rows(self):
        registry = _registry(users=Factory(base={"id": 999}))
        spec = _make_spec(given={"users": [{"id": 1}]})
        result = expand_unit_test(
            spec,
            model="m",
            registry=registry,
            source_file=SRC,
            source_line=1,
            expected_upstreams=["users"],
            auto_fill=True,
        )
        assert result.given == {"users": [{"id": 1}]}
        assert result.auto_filled_upstreams == ()

    def test_skips_upstream_without_matching_factory(self):
        registry = _registry(users=Factory(base={"id": 1}))
        spec = _make_spec(given={"users": [{"factory": "users"}]})
        result = expand_unit_test(
            spec,
            model="m",
            registry=registry,
            source_file=SRC,
            source_line=1,
            # `orders` has no factory of the same name -> skip silently.
            expected_upstreams=["users", "orders"],
            auto_fill=True,
        )
        assert "orders" not in result.given
        assert result.auto_filled_upstreams == ()

    def test_records_multiple_filled_upstreams(self):
        registry = _registry(
            users=Factory(base={"id": 1}),
            orders=Factory(base={"id": 100}),
        )
        spec = _make_spec(given={})
        result = expand_unit_test(
            spec,
            model="m",
            registry=registry,
            source_file=SRC,
            source_line=1,
            expected_upstreams=["users", "orders"],
            auto_fill=True,
        )
        assert set(result.given.keys()) == {"users", "orders"}
        assert sorted(result.auto_filled_upstreams) == ["orders", "users"]

    def test_no_expected_upstreams_means_no_injection(self):
        registry = _registry(users=Factory(base={"id": 1}))
        spec = _make_spec(given={})
        result = expand_unit_test(
            spec,
            model="m",
            registry=registry,
            source_file=SRC,
            source_line=1,
            expected_upstreams=None,
            auto_fill=True,
        )
        assert result.given == {}
        assert result.auto_filled_upstreams == ()
