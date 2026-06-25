"""Factory registry tests: loading from disk and resolving rows."""

from __future__ import annotations

import pytest

from lighttest.factory import (
    DuplicateFactoryError,
    FactoryRegistry,
    InvalidFactoryFileError,
    UnknownFactoryError,
    UnknownTraitError,
)
from lighttest.schema import Factory


class TestRegistryLoad:
    def test_missing_root_returns_empty_registry(self, tmp_path):
        registry = FactoryRegistry.load(tmp_path / "does_not_exist")
        assert len(registry) == 0
        assert registry.names == []

    def test_empty_root_returns_empty_registry(self, tmp_path):
        registry = FactoryRegistry.load(tmp_path)
        assert len(registry) == 0

    def test_single_file_is_loaded(self, tmp_path, write_yaml):
        write_yaml(
            "factories/user.yml",
            """
            factories:
              user:
                base:
                  id: 1
                  name: alice
            """,
        )
        registry = FactoryRegistry.load(tmp_path / "factories")
        assert registry.names == ["user"]
        assert "user" in registry

    def test_multiple_files_are_merged(self, tmp_path, write_yaml):
        write_yaml(
            "factories/users.yml",
            """
            factories:
              user:
                base: {id: 1}
            """,
        )
        write_yaml(
            "factories/orders.yml",
            """
            factories:
              order:
                base: {id: 100}
            """,
        )
        registry = FactoryRegistry.load(tmp_path / "factories")
        assert registry.names == ["order", "user"]

    def test_subdirectories_are_walked(self, tmp_path, write_yaml):
        write_yaml(
            "factories/sub/nested.yml",
            """
            factories:
              nested:
                base: {x: 1}
            """,
        )
        registry = FactoryRegistry.load(tmp_path / "factories")
        assert "nested" in registry

    def test_yaml_extension_variants_are_picked_up(self, tmp_path, write_yaml):
        write_yaml("f/a.yml", "factories: {a: {base: {x: 1}}}\n")
        write_yaml("f/b.yaml", "factories: {b: {base: {x: 2}}}\n")
        registry = FactoryRegistry.load(tmp_path / "f")
        assert registry.names == ["a", "b"]

    def test_empty_yaml_file_is_allowed(self, tmp_path, write_yaml):
        write_yaml("factories/empty.yml", "")
        registry = FactoryRegistry.load(tmp_path / "factories")
        assert len(registry) == 0

    def test_duplicate_name_across_files_raises(self, tmp_path, write_yaml):
        write_yaml(
            "factories/a.yml",
            "factories: {dup: {base: {x: 1}}}\n",
        )
        write_yaml(
            "factories/b.yml",
            "factories: {dup: {base: {x: 2}}}\n",
        )
        with pytest.raises(DuplicateFactoryError) as exc_info:
            FactoryRegistry.load(tmp_path / "factories")
        assert exc_info.value.name == "dup"

    def test_malformed_yaml_raises(self, tmp_path, write_yaml):
        write_yaml("factories/bad.yml", "factories: {oops::::")
        with pytest.raises(InvalidFactoryFileError):
            FactoryRegistry.load(tmp_path / "factories")

    def test_non_mapping_top_level_raises(self, tmp_path, write_yaml):
        write_yaml("factories/list.yml", "- item1\n- item2\n")
        with pytest.raises(InvalidFactoryFileError):
            FactoryRegistry.load(tmp_path / "factories")

    def test_missing_factories_key_raises(self, tmp_path, write_yaml):
        write_yaml("factories/wrong.yml", "not_factories: {}\n")
        with pytest.raises(InvalidFactoryFileError):
            FactoryRegistry.load(tmp_path / "factories")


class TestRegistryResolve:
    def _registry(self, **factories: Factory) -> FactoryRegistry:
        return FactoryRegistry(factories)

    def test_resolve_base_only(self):
        registry = self._registry(user=Factory(base={"id": 1, "name": "alice"}))
        assert registry.resolve("user") == {"id": 1, "name": "alice"}

    def test_resolve_with_trait(self):
        registry = self._registry(
            user=Factory(
                base={"id": 1, "tier": "standard"},
                traits={"premium": {"tier": "premium"}},
            )
        )
        assert registry.resolve("user", trait_name="premium") == {
            "id": 1,
            "tier": "premium",
        }

    def test_resolve_with_override(self):
        registry = self._registry(user=Factory(base={"id": 1, "name": "alice"}))
        assert registry.resolve("user", override={"id": 99}) == {
            "id": 99,
            "name": "alice",
        }

    def test_resolve_precedence_override_beats_trait_beats_base(self):
        registry = self._registry(
            user=Factory(
                base={"id": 1, "tier": "standard", "country": "JP"},
                traits={"premium": {"tier": "premium", "country": "US"}},
            )
        )
        result = registry.resolve(
            "user",
            trait_name="premium",
            override={"country": "DE"},
        )
        assert result == {"id": 1, "tier": "premium", "country": "DE"}

    def test_resolve_deep_merges_nested(self):
        registry = self._registry(
            cfg=Factory(base={"nested": {"x": 10, "y": 20}}),
        )
        result = registry.resolve("cfg", override={"nested": {"y": 999}})
        assert result == {"nested": {"x": 10, "y": 999}}

    def test_resolve_none_override_returns_empty_layer(self):
        registry = self._registry(user=Factory(base={"a": 1}))
        # `override=None` is the same as `override={}`.
        assert registry.resolve("user", override=None) == {"a": 1}

    def test_resolve_returns_independent_dict(self):
        registry = self._registry(user=Factory(base={"a": 1}))
        first = registry.resolve("user")
        first["a"] = 99
        second = registry.resolve("user")
        assert second == {"a": 1}

    def test_unknown_factory_raises_with_known_list(self):
        registry = self._registry(known=Factory(base={}))
        with pytest.raises(UnknownFactoryError) as exc_info:
            registry.resolve("missing")
        assert exc_info.value.name == "missing"
        assert "known" in str(exc_info.value)

    def test_unknown_trait_raises(self):
        registry = self._registry(user=Factory(base={}, traits={"a": {}}))
        with pytest.raises(UnknownTraitError) as exc_info:
            registry.resolve("user", trait_name="missing")
        assert exc_info.value.factory == "user"
        assert exc_info.value.trait == "missing"
