"""Tests for StackManifest — YAML single serialization layer.

Design: Core Stack Installation & Lifecycle — StackManifest
Spec: core-stack §Manifest
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apoch.stack.manifest import StackManifest, StackManifestEntry
from apoch.stack.state import StackState


class TestStackManifestEntry:
    """Verify StackManifestEntry creation."""

    def test_minimal_entry(self):
        """Create an entry with required fields only."""
        entry = StackManifestEntry(
            name="engram",
            version="1.0.0",
            state=StackState.INSTALLED,
        )
        assert entry.name == "engram"
        assert entry.state == StackState.INSTALLED
        assert entry.details == {}

    def test_entry_with_details(self):
        """Create an entry with optional details."""
        entry = StackManifestEntry(
            name="oracle",
            version="2.0.0",
            state=StackState.ACTIVE,
            details={"install_path": "/opt/apoch/oracle"},
        )
        assert entry.details["install_path"] == "/opt/apoch/oracle"


class TestStackManifest:
    """Verify manifest read/write operations."""

    @pytest.fixture
    def manifest(self) -> StackManifest:
        return StackManifest()

    @pytest.fixture
    def temp_manifest_path(self, tmp_path: Path) -> Path:
        return tmp_path / "manifest.yaml"

    def test_empty_manifest_data(self, manifest: StackManifest):
        """An empty manifest returns an empty dict."""
        data = manifest.data
        assert data == {}

    def test_set_and_get_entry(self, manifest: StackManifest):
        """A component can be added and retrieved."""
        entry = StackManifestEntry(name="engram", version="1.0.0", state=StackState.INSTALLED)
        manifest.set("engram", entry)
        retrieved = manifest.get("engram")
        assert retrieved is not None
        assert retrieved.name == "engram"
        assert retrieved.state == StackState.INSTALLED

    def test_get_nonexistent_returns_none(self, manifest: StackManifest):
        """get() returns None for an unknown component."""
        assert manifest.get("nonexistent") is None

    def test_remove_entry(self, manifest: StackManifest):
        """A component can be removed from the manifest."""
        entry = StackManifestEntry(name="engram", version="1.0.0", state=StackState.INSTALLED)
        manifest.set("engram", entry)
        manifest.remove("engram")
        assert manifest.get("engram") is None

    def test_list_entries(self, manifest: StackManifest):
        """list() returns all entries."""
        manifest.set(
            "a",
            StackManifestEntry(name="a", version="1.0", state=StackState.INSTALLED),
        )
        manifest.set(
            "b",
            StackManifestEntry(name="b", version="2.0", state=StackState.ACTIVE),
        )
        entries = manifest.list()
        assert len(entries) == 2
        names = {e.name for e in entries}
        assert names == {"a", "b"}

    def test_save_and_load(self, manifest: StackManifest, temp_manifest_path: Path):
        """A manifest can be saved to disk and reloaded."""
        entry = StackManifestEntry(
            name="engram",
            version="1.0.0",
            state=StackState.INSTALLED,
            details={"path": "/tmp/test"},
        )
        manifest.set("engram", entry)
        manifest.save(temp_manifest_path)

        # Verify the file exists and is valid YAML
        assert temp_manifest_path.exists()
        with open(temp_manifest_path) as f:
            raw = yaml.safe_load(f)
        assert raw is not None
        assert "engram" in raw
        assert raw["engram"]["version"] == "1.0.0"
        assert raw["engram"]["state"] == "installed"

        # Load into a new manifest instance
        manifest2 = StackManifest()
        loaded = manifest2.load(temp_manifest_path)
        assert loaded is True
        retrieved = manifest2.get("engram")
        assert retrieved is not None
        assert retrieved.version == "1.0.0"
        assert retrieved.state == StackState.INSTALLED
        assert retrieved.details["path"] == "/tmp/test"

    def test_load_nonexistent_file(self, manifest: StackManifest):
        """Loading a non-existent file returns False."""
        result = manifest.load(Path("/nonexistent/manifest.yaml"))
        assert result is False

    def test_save_creates_parent_dir(self, manifest: StackManifest, tmp_path: Path):
        """Saving to a nested path creates parent directories."""
        entry = StackManifestEntry(name="x", version="1.0", state=StackState.UNKNOWN)
        manifest.set("x", entry)
        deep_path = tmp_path / "a" / "b" / "c" / "manifest.yaml"
        manifest.save(deep_path)
        assert deep_path.exists()
