"""Unit tests for `slimtest.deep_merge.deep_merge`."""

from __future__ import annotations

from slimtest.deep_merge import deep_merge


class TestFlatMerge:
    def test_non_overlapping_keys_are_unioned(self):
        result = deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_override_wins_on_scalar_collision(self):
        result = deep_merge({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_empty_override_returns_copy_of_base(self):
        base = {"a": 1}
        result = deep_merge(base, {})
        assert result == base
        assert result is not base  # must be a copy

    def test_empty_base_returns_copy_of_override(self):
        override = {"a": 1}
        result = deep_merge({}, override)
        assert result == override
        assert result is not override


class TestNestedMerge:
    def test_nested_dicts_are_merged_recursively(self):
        base = {"a": 1, "nested": {"x": 10, "y": 20}}
        override = {"nested": {"y": 999, "z": 30}}
        assert deep_merge(base, override) == {
            "a": 1,
            "nested": {"x": 10, "y": 999, "z": 30},
        }

    def test_deeply_nested_merge(self):
        base = {"a": {"b": {"c": {"d": 1, "e": 2}}}}
        override = {"a": {"b": {"c": {"e": 99}}}}
        assert deep_merge(base, override) == {"a": {"b": {"c": {"d": 1, "e": 99}}}}

    def test_scalar_to_dict_replacement(self):
        # base value is scalar, override is dict -> override wins (no merge).
        result = deep_merge({"a": 1}, {"a": {"x": 1}})
        assert result == {"a": {"x": 1}}

    def test_dict_to_scalar_replacement(self):
        # base value is dict, override is scalar -> scalar wins (no merge).
        result = deep_merge({"a": {"x": 1}}, {"a": 5})
        assert result == {"a": 5}


class TestNullSemantics:
    def test_explicit_none_in_override_overwrites_base(self):
        # design.md §6.4: null overrides, not deletes.
        result = deep_merge({"a": 1}, {"a": None})
        assert result == {"a": None}

    def test_explicit_none_in_override_overwrites_dict_in_base(self):
        result = deep_merge({"a": {"x": 1}}, {"a": None})
        assert result == {"a": None}

    def test_none_only_in_base_is_preserved(self):
        result = deep_merge({"a": None}, {"b": 2})
        assert result == {"a": None, "b": 2}


class TestListSemantics:
    def test_list_in_override_replaces_list_in_base(self):
        # Lists are NOT merged element-wise.
        result = deep_merge({"a": [1, 2, 3]}, {"a": [9]})
        assert result == {"a": [9]}

    def test_list_replaces_dict(self):
        result = deep_merge({"a": {"x": 1}}, {"a": [1, 2]})
        assert result == {"a": [1, 2]}


class TestImmutability:
    def test_base_is_not_mutated(self):
        base = {"a": {"x": 1}}
        deep_merge(base, {"a": {"y": 2}})
        assert base == {"a": {"x": 1}}

    def test_override_is_not_mutated(self):
        override = {"a": {"y": 2}}
        deep_merge({"a": {"x": 1}}, override)
        assert override == {"a": {"y": 2}}

    def test_nested_dicts_in_result_are_independent(self):
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        result = deep_merge(base, override)
        result["a"]["z"] = 3
        # If we shared references, base would now have z.
        assert "z" not in base["a"]
        assert "z" not in override["a"]
