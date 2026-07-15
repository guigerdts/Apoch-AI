"""StackManifest — single YAML serialization layer for stack state.

The manifest is a YAML file persisted at ``StackPaths.manifest_path()``
that records every known component and its current state.

Design: Core Stack Installation & Lifecycle — StackManifest
Spec: core-stack §Manifest
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from apoch.stack.exceptions import StackManifestError
from apoch.stack.state import StackState


@dataclass
class StackManifestEntry:
    """A single entry in the stack manifest."""

    name: str
    version: str
    state: StackState
    details: dict[str, Any] = field(default_factory=dict)


class StackManifest:
    """In-memory representation of the stack manifest.

    Thread-safety is not required — the manifest is serialised under
    the stack lock.
    """

    def __init__(self) -> None:
        self._entries: dict[str, StackManifestEntry] = {}

    # ── Accessors ────────────────────────────────────────────────────

    @property
    def data(self) -> dict[str, StackManifestEntry]:
        """Return the raw entries dict (read-only snapshot)."""
        return dict(self._entries)

    def get(self, name: str) -> StackManifestEntry | None:
        """Return the entry for *name*, or ``None`` if unknown."""
        return self._entries.get(name)

    def set(self, name: str, entry: StackManifestEntry) -> None:
        """Set or update the entry for *name*."""
        self._entries[name] = entry

    def remove(self, name: str) -> None:
        """Remove the entry for *name*, if present."""
        self._entries.pop(name, None)

    def list(self) -> tuple[StackManifestEntry, ...]:
        """Return all entries as a tuple."""
        return tuple(self._entries.values())

    # ── Persistence ──────────────────────────────────────────────────

    def load(self, path: Path) -> bool:
        """Load manifest entries from a YAML file.

        Args:
            path: Path to the manifest file.

        Returns:
            ``True`` if the file was loaded, ``False`` if it does not exist.
        """
        if not path.exists():
            return False

        with open(path) as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        for name, data in raw.items():
            state_value = data.get("state", "unknown")
            try:
                state = StackState(state_value)
            except ValueError:
                state = StackState.UNKNOWN

            self._entries[name] = StackManifestEntry(
                name=name,
                version=data.get("version", "0.0.0"),
                state=state,
                details=data.get("details", {}),
            )
        return True

    def save(self, path: Path) -> None:
        """Persist all entries to a YAML file.

        Args:
            path: Destination file path.

        Raises:
            StackManifestError: If the file cannot be written.
        """
        raw: dict[str, Any] = {}
        for name, entry in self._entries.items():
            raw[name] = {
                "version": entry.version,
                "state": entry.state.value,
            }
            if entry.details:
                raw[name]["details"] = entry.details

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                yaml.dump(raw, f, default_flow_style=False, sort_keys=False)
        except OSError as exc:
            msg = f"Cannot write manifest to {path}: {exc}"
            raise StackManifestError(msg) from exc
