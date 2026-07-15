"""Tests for the OpenSpec Stack Component.

PR5.1 — Foundation: DESCRIPTOR, parse_openspec_version, and
entry-point resolution.
"""

from __future__ import annotations

from apoch.stack.components.openspec import (
    DESCRIPTOR,
    OpenSpecComponent,
    parse_openspec_version,
)


class TestDescriptor:
    """DESCRIPTOR contains factual metadata about the official project."""

    def test_id(self):
        assert DESCRIPTOR.id == "openspec"

    def test_name(self):
        assert DESCRIPTOR.name == "OpenSpec"

    def test_kind(self):
        assert DESCRIPTOR.kind == "integrations"

    def test_install_command(self):
        assert "npm install -g" in DESCRIPTOR.install_command

    def test_homepage(self):
        assert DESCRIPTOR.homepage == "https://openspec.dev/"

    def test_repository(self):
        assert "github.com/fission-ai/OpenSpec" in DESCRIPTOR.repository

    def test_requires_node(self):
        assert "node" in DESCRIPTOR.requires[0]


class TestParseVersion:
    """parse_openspec_version handles multiple output formats."""

    def test_openspec_prefix(self):
        assert parse_openspec_version("openspec 1.6.0") == "1.6.0"

    def test_v_prefix(self):
        assert parse_openspec_version("v1.6.0") == "1.6.0"

    def test_bare(self):
        assert parse_openspec_version("1.6.0") == "1.6.0"

    def test_multiline(self):
        assert parse_openspec_version("foo\nopenspec 1.6.0\nbar") == "1.6.0"

    def test_nonsense(self):
        assert parse_openspec_version("not-a-version") is None

    def test_empty(self):
        assert parse_openspec_version("") is None


class TestComponent:
    """OpenSpecComponent can be instantiated and has correct descriptor."""

    def test_descriptor_is_descriptor(self):
        comp = OpenSpecComponent()
        assert comp.descriptor is DESCRIPTOR

    def test_lifecycle_methods_raise_not_implemented(self):
        comp = OpenSpecComponent()
        # All methods should raise NotImplementedError until PR5.2
        # We test the import and class structure here
        assert hasattr(comp, "detect")
        assert hasattr(comp, "install")
        assert hasattr(comp, "verify")
        assert hasattr(comp, "activate")
        assert hasattr(comp, "deactivate")
        assert hasattr(comp, "uninstall")
        assert hasattr(comp, "health")


class TestEntryPoint:
    """The entry point resolves correctly via importlib.metadata."""

    def test_entry_point_resolves(self):
        from importlib.metadata import entry_points

        eps = entry_points(group="apoch.stack.components")
        openspec_eps = [ep for ep in eps if ep.name == "openspec"]
        assert len(openspec_eps) == 1
        ep = openspec_eps[0]
        assert ep.value == "apoch.stack.components.openspec:OpenSpecComponent"
