"""Stack component descriptor — identifies and describes a stackable component.

Design: Core Stack Installation & Lifecycle — StackComponent Interface
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ComponentKind = Literal["integrations", "store", "services"]


@dataclass(frozen=True)
class StackDescriptor:
    """Immutable descriptor for a registered stack component.

    Apoch does **not** implement components.  It only acts as an adapter
    to each official project using its public interface.  Fields like
    *install_command*, *homepage*, *repository*, and *docs_url* must
    come from the official project documentation — never hardcoded from
    assumptions.

    Attributes:
        id:              Stable machine-readable identifier
                         (e.g. ``"openspec"``).  Independent of display
                         *name* so renaming never breaks config.
        name:            Short display name (e.g. ``"OpenSpec"``).
        kind:            Component category — ``"integrations"``,
                         ``"store"``, or ``"services"``.
        version:         Semantic version string of **this descriptor**
                         (the component format/API version, not the
                         installed package version).
        description:     Human-readable description (one line).
        entry_point:     Dot-separated Python path to the
                         ``StackComponent`` subclass
                         (e.g. ``"apoch.stack.components.openspec:OpenSpecComponent"``).
        dependencies:    Names of components that MUST be installed first.
        install_command: Exact official install command
                         (e.g. ``"npm install -g @fission-ai/openspec@latest"``).
        install_manager: Package manager name (e.g. ``"npm"``, ``"pip"``,
                         ``"uv"``).
        homepage:        Project homepage URL.
        repository:      Source repository URL.
        docs_url:        Official documentation URL (may be same as
                         *homepage*).
        requires:        Prerequisite specifications such as
                         ``"node>=20.19.0"``.
        min_version:     Minimum supported semantic version (inclusive).
                         Below this → ``OUTDATED``.
        max_version:     Maximum supported semantic version (inclusive).
                         Above this → ``UNSUPPORTED``.
        capabilities:    Features the component exposes to the platform.
    """

    name: str
    kind: ComponentKind
    version: str
    description: str
    entry_point: str
    id: str = ""
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    install_command: str = ""
    install_manager: str = ""
    homepage: str = ""
    repository: str = ""
    docs_url: str = ""
    requires: tuple[str, ...] = field(default_factory=tuple)
    min_version: str = ""
    max_version: str = ""
    capabilities: tuple[str, ...] = field(default_factory=tuple)
