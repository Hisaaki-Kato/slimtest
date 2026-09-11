"""Tests for `slimtest.manifest`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from slimtest.manifest import (
    AmbiguousUpstreamError,
    InvalidManifestError,
    Manifest,
    ManifestNotFoundError,
    UpstreamRef,
    try_load_manifest,
)

# -- helpers --------------------------------------------------------


def _write_manifest(project_root: Path, data: dict) -> Path:
    target = project_root / "target"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _manifest_dict(
    models: list[str],
    sources: list[tuple[str, str]],
    depends_on: dict[str, list[str]] | None = None,
) -> dict:
    """Build a tiny manifest.json.

    `sources` is a list of (source_name, table_name); `depends_on` maps
    model_name -> list of upstream node ids the model depends on.
    """
    deps = depends_on or {}
    nodes = {}
    for m in models:
        entry: dict = {"resource_type": "model", "name": m}
        if m in deps:
            entry["depends_on"] = {"nodes": deps[m]}
        nodes[f"model.proj.{m}"] = entry
    src_nodes = {
        f"source.proj.{s}.{t}": {"name": t, "source_name": s} for s, t in sources
    }
    return {"nodes": nodes, "sources": src_nodes}


# -- UpstreamRef ----------------------------------------------------


class TestUpstreamRef:
    def test_ref_renders_correctly(self):
        ref = UpstreamRef(kind="ref", name="my_model")
        assert ref.to_input_expression() == "ref('my_model')"

    def test_source_renders_correctly(self):
        ref = UpstreamRef(kind="source", name="my_table", source_name="my_src")
        assert ref.to_input_expression() == "source('my_src', 'my_table')"

    def test_qualified_versioned_ref_renders_correctly(self):
        ref = UpstreamRef(
            kind="ref", name="orders", package_name="warehouse", version=2
        )
        assert ref.to_input_expression() == "ref('warehouse', 'orders', version=2)"


# -- Manifest.load --------------------------------------------------


class TestManifestLoad:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ManifestNotFoundError):
            Manifest.load(tmp_path)

    def test_malformed_json_raises(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        (target / "manifest.json").write_text("not json{", encoding="utf-8")
        with pytest.raises(InvalidManifestError):
            Manifest.load(tmp_path)

    def test_non_object_top_level_raises(self, tmp_path):
        _write_manifest(tmp_path, [])  # type: ignore[arg-type]
        with pytest.raises(InvalidManifestError):
            Manifest.load(tmp_path)

    def test_empty_manifest_loads_empty(self, tmp_path):
        _write_manifest(tmp_path, {"nodes": {}, "sources": {}})
        m = Manifest.load(tmp_path)
        assert m.models == frozenset()
        assert m.sources_by_table == {}

    def test_models_are_collected(self, tmp_path):
        _write_manifest(tmp_path, _manifest_dict(["a", "b"], []))
        m = Manifest.load(tmp_path)
        assert m.models == frozenset({"a", "b"})

    def test_sources_are_collected(self, tmp_path):
        _write_manifest(
            tmp_path,
            _manifest_dict([], [("raw", "events"), ("raw", "orders")]),
        )
        m = Manifest.load(tmp_path)
        assert m.sources_by_table == {"events": ["raw"], "orders": ["raw"]}

    def test_non_model_nodes_are_skipped(self, tmp_path):
        data = {
            "nodes": {
                "model.proj.a": {"resource_type": "model", "name": "a"},
                "test.proj.x": {"resource_type": "test", "name": "x"},
                "seed.proj.s": {"resource_type": "seed", "name": "s"},
            },
            "sources": {},
        }
        _write_manifest(tmp_path, data)
        m = Manifest.load(tmp_path)
        assert m.models == frozenset({"a"})


# -- Manifest.resolve -----------------------------------------------


class TestManifestResolve:
    def _manifest(
        self,
        models: list[str] | None = None,
        sources: list[tuple[str, str]] | None = None,
    ) -> Manifest:
        return Manifest._from_dict(_manifest_dict(models or [], sources or []))

    def test_known_model_resolves_to_ref(self):
        m = self._manifest(models=["foo"])
        assert m.resolve("foo") == UpstreamRef(kind="ref", name="foo")

    def test_known_source_resolves_to_source(self):
        m = self._manifest(sources=[("raw", "events")])
        assert m.resolve("events") == UpstreamRef(
            kind="source", name="events", source_name="raw"
        )

    def test_unknown_falls_back_to_ref(self):
        m = self._manifest()
        assert m.resolve("unknown") == UpstreamRef(kind="ref", name="unknown")

    def test_model_and_source_collision_raises(self):
        m = self._manifest(models=["foo"], sources=[("raw", "foo")])
        with pytest.raises(AmbiguousUpstreamError) as exc:
            m.resolve("foo")
        assert "ref('foo')" in str(exc.value)
        assert "source('raw', 'foo')" in str(exc.value)

    def test_table_in_multiple_sources_raises(self):
        m = self._manifest(sources=[("a", "foo"), ("b", "foo")])
        with pytest.raises(AmbiguousUpstreamError):
            m.resolve("foo")

    @pytest.mark.parametrize(
        ("expression", "rendered"),
        [
            ("ref('orders', version=2)", "ref('orders', version=2)"),
            ("ref('pkg', 'orders', v=2)", "ref('pkg', 'orders', version=2)"),
            ("source('raw', 'orders')", "source('raw', 'orders')"),
        ],
    )
    def test_explicit_expressions_are_safely_parsed(self, expression, rendered):
        assert self._manifest().resolve(expression).to_input_expression() == rendered

    def test_bare_name_is_scoped_to_tested_model_dependencies(self):
        data = {
            "metadata": {"project_name": "app"},
            "nodes": {
                "model.app.m": {
                    "resource_type": "model",
                    "name": "m",
                    "package_name": "app",
                    "depends_on": {"nodes": ["source.app.raw.orders"]},
                },
                "model.vendor.orders": {
                    "resource_type": "model",
                    "name": "orders",
                    "package_name": "vendor",
                },
            },
            "sources": {
                "source.app.raw.orders": {
                    "name": "orders",
                    "source_name": "raw",
                    "package_name": "app",
                }
            },
        }
        manifest = Manifest._from_dict(data)
        assert manifest.resolve("orders", model_name="m").to_input_expression() == (
            "source('raw', 'orders')"
        )

    def test_versioned_dependency_preserves_name_package_and_version(self):
        data = {
            "metadata": {"project_name": "app"},
            "nodes": {
                "model.app.m": {
                    "resource_type": "model",
                    "name": "m",
                    "package_name": "app",
                    "depends_on": {"nodes": ["model.vendor.orders.v2"]},
                },
                "model.vendor.orders.v2": {
                    "resource_type": "model",
                    "name": "orders",
                    "package_name": "vendor",
                    "version": 2,
                },
            },
            "sources": {},
        }
        manifest = Manifest._from_dict(data)
        assert manifest.get_upstreams("m") == ["orders"]
        assert manifest.resolve("orders", model_name="m").to_input_expression() == (
            "ref('vendor', 'orders', version=2)"
        )

    def test_model_versions_with_same_dependency_share_scope(self):
        data = {
            "metadata": {"project_name": "app"},
            "nodes": {
                "model.app.m.v1": {
                    "resource_type": "model",
                    "name": "m",
                    "package_name": "app",
                    "version": 1,
                    "depends_on": {"nodes": ["source.app.raw.orders"]},
                },
                "model.app.m.v2": {
                    "resource_type": "model",
                    "name": "m",
                    "package_name": "app",
                    "version": 2,
                    "depends_on": {"nodes": ["source.app.raw.orders"]},
                },
            },
            "sources": {
                "source.app.raw.orders": {
                    "name": "orders",
                    "source_name": "raw",
                    "package_name": "app",
                }
            },
        }
        manifest = Manifest._from_dict(data)
        assert manifest.get_upstreams("m") == ["orders"]
        assert manifest.resolve("orders", model_name="m").kind == "source"
        assert manifest.upstream_matches("m", "orders", "source('raw', 'orders')")

    def test_seed_and_snapshot_are_refable(self):
        data = {
            "nodes": {
                "seed.app.countries": {"resource_type": "seed", "name": "countries"},
                "snapshot.app.users": {"resource_type": "snapshot", "name": "users"},
            },
            "sources": {},
        }
        manifest = Manifest._from_dict(data)
        assert manifest.resolve("countries").kind == "ref"
        assert manifest.resolve("users").kind == "ref"


# -- try_load_manifest ----------------------------------------------


def test_try_load_returns_none_for_missing_file(tmp_path):
    assert try_load_manifest(tmp_path) is None


def test_try_load_returns_manifest_when_present(tmp_path):
    _write_manifest(tmp_path, _manifest_dict(["a"], []))
    m = try_load_manifest(tmp_path)
    assert m is not None
    assert "a" in m.models


# -- get_upstreams ---------------------------------------------------


class TestManifestUpstreams:
    def _manifest(self, depends_on, models=("foo",), sources=()):
        return Manifest._from_dict(
            _manifest_dict(list(models), list(sources), depends_on)
        )

    def test_returns_empty_for_unknown_model(self):
        m = self._manifest({})
        assert m.get_upstreams("not_a_model") == []

    def test_returns_empty_when_model_has_no_depends_on(self):
        m = self._manifest({})  # foo present, no depends_on entry
        assert m.get_upstreams("foo") == []

    def test_extracts_bare_names_from_model_refs(self):
        m = self._manifest(
            {"foo": ["model.proj.bar", "model.proj.baz"]},
            models=("foo", "bar", "baz"),
        )
        assert m.get_upstreams("foo") == ["bar", "baz"]

    def test_extracts_bare_names_from_source_deps(self):
        m = self._manifest(
            {"foo": ["source.proj.app.events", "source.proj.app.orders"]},
            sources=[("app", "events"), ("app", "orders")],
        )
        assert m.get_upstreams("foo") == ["events", "orders"]

    def test_mixed_refs_and_sources(self):
        m = self._manifest(
            {"foo": ["model.proj.bar", "source.proj.app.events"]},
            models=("foo", "bar"),
            sources=[("app", "events")],
        )
        assert m.get_upstreams("foo") == ["bar", "events"]

    def test_preserves_declaration_order(self):
        m = self._manifest(
            {"foo": ["model.proj.c", "model.proj.a", "model.proj.b"]},
            models=("foo", "a", "b", "c"),
        )
        assert m.get_upstreams("foo") == ["c", "a", "b"]

    def test_duplicates_are_dropped(self):
        m = self._manifest(
            {"foo": ["model.proj.bar", "model.proj.bar"]},
            models=("foo", "bar"),
        )
        assert m.get_upstreams("foo") == ["bar"]
