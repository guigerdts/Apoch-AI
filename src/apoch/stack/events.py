"""Event type constants emitted by the Stack Manager.

Components observe these events to react to lifecycle changes.

Design: Core Stack Installation & Lifecycle — Events-Only Observability
"""

from __future__ import annotations

# ── Lifecycle event types ───────────────────────────────────────────
COMPONENT_INSTALLING = "stack.component.installing"
COMPONENT_INSTALLED = "stack.component.installed"
COMPONENT_UNINSTALLING = "stack.component.uninstalling"
COMPONENT_UNINSTALLED = "stack.component.uninstalled"
COMPONENT_ACTIVATING = "stack.component.activating"
COMPONENT_ACTIVATED = "stack.component.activated"
COMPONENT_DEACTIVATING = "stack.component.deactivating"
COMPONENT_DEACTIVATED = "stack.component.deactivated"
COMPONENT_VERIFYING = "stack.component.verifying"
COMPONENT_VERIFIED = "stack.component.verified"
COMPONENT_ERROR = "stack.component.error"
COMPONENT_STATE_CHANGED = "stack.component.state_changed"

# ── Error event types ───────────────────────────────────────────────
STACK_LOCK_ACQUIRED = "stack.lock.acquired"
STACK_LOCK_RELEASED = "stack.lock.released"
STACK_LOCK_FAILED = "stack.lock.failed"

__all__ = [
    "COMPONENT_INSTALLING",
    "COMPONENT_INSTALLED",
    "COMPONENT_UNINSTALLING",
    "COMPONENT_UNINSTALLED",
    "COMPONENT_ACTIVATING",
    "COMPONENT_ACTIVATED",
    "COMPONENT_DEACTIVATING",
    "COMPONENT_DEACTIVATED",
    "COMPONENT_VERIFYING",
    "COMPONENT_VERIFIED",
    "COMPONENT_ERROR",
    "COMPONENT_STATE_CHANGED",
    "STACK_LOCK_ACQUIRED",
    "STACK_LOCK_RELEASED",
    "STACK_LOCK_FAILED",
]
