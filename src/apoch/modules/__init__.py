"""First-party Apoch-AI modules.

Each sub-package implements a concrete module following the Module ABC
lifecycle contract (see ``apoch.core.module``).

Modules registered here are discoverable via the ``apoch.modules`` entry
point group in ``pyproject.toml``.
"""

from __future__ import annotations

__all__ = ["chronicle", "optimizer", "pulse"]
