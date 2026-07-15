"""Stack installation state machine — FSM specification.

This module is the **single source of truth** for:

* The 11 enum values of :class:`StackState` and their semantics.
* The valid transition table (``_TRANSITIONS``).
* The :func:`derive_state` pure function that maps (descriptor →
  observed info) → state.
* The distinction between ``ERROR``, ``BROKEN``, ``OUTDATED``, and
  ``UNSUPPORTED`` — four states that are easy to confuse.

Design: Core Stack Installation & Lifecycle — State Model

.. rst-class:: opencode-state-diagram

State diagram (text)::

                               ┌─────────────────────┐
                               │       UNKNOWN       │
                               └──────┬──────────────┘
                                      │ discover / first detect
                                      ▼
                            ┌─────────────────────┐
                            │    NOT_INSTALLED    │
                            └──────┬──────────────┘
                                   │ install()
                                   ▼
                            ┌─────────────────────┐
                     ┌─────│     INSTALLING      │─────┐
                     │     └──────────┬──────────┘     │
                     │                │ success        │ error
                     │                ▼                ▼
                     │     ┌─────────────────────┐ ┌──────┐
                     │     │     INSTALLED       │ │ERROR │
                     │     └──┬──┬──┬──┬──┬──┬──┘ └──┬───┘
                     │        │  │  │  │  │  │       │
                     │        │  │  │  │  │  │       │ retry
                     │        │  │  │  │  │  │       │
                     │        │  │  │  │  │  │       ▼
                     │        │  │  │  │  │  │ ┌──────────────┐
                     │        │  │  │  │  │  │ │ NOT_INSTALLED│
                     │        │  │  │  │  │  │ └──────────────┘
                     │    activate verify  │ verify
                     │        │  detect()  │  fails
                     │        ▼  outdated  ▼
                     │  ┌────────┐  ┌───────────┐
                     │  │ ACTIVE │  │  OUTDATED │
                     │  └───┬────┘  └─────┬─────┘
                     │      │ deactivate  │
                     │      ▼             │ update()
                     │  ┌──────────┐      │
                     │  │ INACTIVE │      ▼
                     │  └────┬─────┘  ┌──────────┐
                     │       │        │ INSTALLED │
                     │       │reactivate        │
                     │       └─────────┘         │ update()
                     │          verify            │
                     │            fails            │
                     │             ▼               ▼
                     │      ┌──────────┐    ┌──────────────┐
                     │      │  BROKEN  │    │  UNSUPPORTED │
                     │      └────┬─────┘    └──────┬───────┘
                     │           │                 │
                     │           │ repair()        │ upgrade
                     │           ▼                 ▼
                     │     ┌──────────┐      (manual — no auto
                     │     │INSTALLED │       transition from
                     │     └──────────┘       UNSUPPORTED)
                     │
                     │     INSTALLED → REMOVED (uninstall)
                     │         │
                     │         ▼
                     │  ┌─────────────────────┐
                     │  │       REMOVED       │
                     │  └──────┬──────────────┘
                     │         │ (forget)
                     │         ▼
                     │  ┌─────────────────────┐
                     └─▶│       UNKNOWN       │
                        └─────────────────────┘


Transition table: see ``_TRANSITIONS`` below.  Every state can reach
``ERROR`` via a failed operation (not shown on every arrow for clarity).


Semantic reference (each state in detail):

================ =======================================================
State            Meaning
================ =======================================================
UNKNOWN          No information available — initial default.
NOT_INSTALLED    Not found on the system.
INSTALLING       Installation in progress (not yet usable).
INSTALLED        Present, compatible version.
ACTIVE           Installed and configured/available for use.
INACTIVE         Installed but disabled / not configured.
OUTDATED         Installed but version *below* minimum required.
UNSUPPORTED      Installed but version *above* maximum supported.
BROKEN           Installed but integrity verification failed.
ERROR            Unexpected failure during an operation.
REMOVED          Previously installed, now removed.
================ =======================================================


Distinguishing ERROR, BROKEN, OUTDATED, UNSUPPORTED
----------------------------------------------------

These four are often confused.  The key distinction:

``ERROR``
    An **operation** failed (install, uninstall, activate, ...).  It is
    a transient state — retrying the operation may succeed.  ERROR is
    set by the :class:`~apoch.stack.manager.StackManager` when a
    component raises or returns ``OperationResult(success=False)``.
    Transition out via ``retry`` → ``NOT_INSTALLED`` (fresh start).

``BROKEN``
    A **verification** failed.  The component IS installed but its
    integrity check failed — e.g. missing files, checksum mismatch.
    Unlike ERROR, the component itself is in an invalid state that
    won't be fixed by a retry.  Transition out via ``repair()`` →
    ``INSTALLED`` (or manually uninstall).

``OUTDATED``
    The component IS installed and working, but its version is below
    ``StackDescriptor.min_version``.  It may still function, but is
    missing features or bugfixes.  Derived by :func:`derive_state` —
    never set by operations.  Transition out via ``update()`` →
    ``INSTALLED``.

``UNSUPPORTED``
    The component IS installed but its version exceeds
    ``StackDescriptor.max_version``.  It may be a future version with
    breaking changes.  Also derived by :func:`derive_state`.  The
    recommended action is an external upgrade of the platform itself
    (raise the descriptor's ``max_version``).  No automatic transition
    — only ``→ ERROR`` if an operation is attempted.

In short:

=============== =========== ============= ========= ====================
State           Set by      Component     Action    Resolution
                           works?
=============== =========== ============= ========= ====================
ERROR           operation   Maybe         Retry     Retry the operation
BROKEN          verify      No            Repair    Fix integrity
OUTDATED        detect()    Yes (limited) Update    Update component
UNSUPPORTED     detect()    Maybe         N/A       Upgrade platform
=============== =========== ============= ========= ====================


:func:`derive_state` return values
-----------------------------------

:func:`derive_state` is a pure function — no I/O, no side effects.
It compares declarative constraints (``StackDescriptor``) against
factual observations (``ComponentInfo`` from ``detect()``).

+--------------------------+------------------------------------------+
| Condition                | Returns                                  |
+==========================+==========================================+
| ``not info.installed``   | ``NOT_INSTALLED``                        |
+--------------------------+------------------------------------------+
| ``info.version`` is      | ``NOT_INSTALLED`` (no version → treat as |
| ``None`` or unparseable  | missing)                                 |
+--------------------------+------------------------------------------+
| ``version < min_version``| ``OUTDATED``                             |
+--------------------------+------------------------------------------+
| ``version > max_version``| ``UNSUPPORTED``                          |
+--------------------------+------------------------------------------+
| Otherwise                | ``INSTALLED``                            |
+--------------------------+------------------------------------------+

``min_version`` is evaluated **before** ``max_version``, so a component
that is simultaneously below min AND above max will be reported as
``OUTDATED``, never ``UNSUPPORTED``.


Flow examples (detect → derive_state → verify)
------------------------------------------------

Happy path (component at correct version)::

    component.detect()
        ↓
    ComponentInfo(installed=True, version="1.2.3")
        ↓
    derive_state(descriptor, info)
        → StackState.INSTALLED
        ↓
    verify()     ← only runs if state is INSTALLED (not NOT_INSTALLED)
        ↓
    OperationResult(success=True)
        → status stays INSTALLED

Outdated component::

    component.detect()
        ↓
    ComponentInfo(installed=True, version="1.0.0")
        ↓
    descriptor.min_version = "2.0.0"
        ↓
    derive_state(descriptor, info)
        → StackState.OUTDATED    ← no verify() call (state is diagnostic)
        ↓
    status set to OUTDATED
        ↓
    User runs ``apoch stack update <name>``
        → update() → INSTALLED

Verify failure::

    component.detect()
        ↓
    ComponentInfo(installed=True, version="1.2.3")
        ↓
    derive_state(descriptor, info)
        → StackState.INSTALLED
        ↓
    verify()
        ↓
    OperationResult(success=False, message="missing binary")
        → status set to BROKEN

Not installed::

    component.detect()
        ↓
    ComponentInfo(installed=False)
        ↓
    derive_state(descriptor, info)
        → StackState.NOT_INSTALLED
        ↓
    verify() short-circuits → returns early
        → "component not installed"
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from packaging.version import InvalidVersion, Version

from apoch.stack.descriptor import StackDescriptor


class StackState(Enum):
    """Installation state of a stack component.

    The state machine follows these allowed transitions::

        NOT_INSTALLED → INSTALLING → INSTALLED → ACTIVE
        ACTIVE → INACTIVE
        INACTIVE → INSTALLED
        INSTALLED → ERROR | OUTDATED | BROKEN
        OUTDATED → INSTALLED | ERROR
        BROKEN → INSTALLED | ERROR
        ERROR → NOT_INSTALLED
        INSTALLED → REMOVED

    Semantic reference:

    ================ ===================================================
    State            Meaning
    ================ ===================================================
    UNKNOWN          No information available (initial / default).
    NOT_INSTALLED    Not found on the system.
    INSTALLING       Installation in progress.
    INSTALLED        Present and compatible.
    ACTIVE           Available for use (instantiated / configured).
    INACTIVE         Installed but disabled / not configured.
    OUTDATED         Installed but version below minimum required.
    UNSUPPORTED      Installed but version exceeds maximum supported.
    BROKEN           Detected but invalid — verification failed.
    ERROR            Error during an operation.
    REMOVED          Previously installed, now removed.
    ================ ===================================================
    """

    UNKNOWN = "unknown"
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    INSTALLED = "installed"
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUTDATED = "outdated"
    UNSUPPORTED = "unsupported"
    BROKEN = "broken"
    ERROR = "error"
    REMOVED = "removed"

    def can_transition_to(self, target: StackState) -> bool:
        """Return ``True`` if a transition from ``self`` to ``target`` is valid."""
        return target in _TRANSITIONS.get(self, ())

    def __str__(self) -> str:
        return self.value


# ── Transition table ──────────────────────────────────────────────────
_TRANSITIONS: Final[dict[StackState, tuple[StackState, ...]]] = {
    StackState.UNKNOWN: (StackState.NOT_INSTALLED,),
    StackState.NOT_INSTALLED: (StackState.INSTALLING,),
    StackState.INSTALLING: (StackState.INSTALLED, StackState.ERROR),
    StackState.INSTALLED: (
        StackState.ACTIVE,
        StackState.ERROR,
        StackState.REMOVED,
        StackState.OUTDATED,
        StackState.BROKEN,
    ),
    StackState.ACTIVE: (StackState.INACTIVE, StackState.ERROR),
    StackState.INACTIVE: (StackState.INSTALLED,),
    StackState.OUTDATED: (StackState.INSTALLED, StackState.ERROR),
    StackState.UNSUPPORTED: (StackState.ERROR,),
    StackState.BROKEN: (StackState.INSTALLED, StackState.ERROR),
    StackState.ERROR: (StackState.NOT_INSTALLED,),
    StackState.REMOVED: (StackState.UNKNOWN,),
}


# ── Version helpers ───────────────────────────────────────────────────


def _parse_version(value: str | None) -> Version | None:
    """Parse *value* into a ``packaging.version.Version``, or return ``None``."""
    if value is None:
        return None
    try:
        return Version(value)
    except InvalidVersion:
        return None


# ── State derivation ─────────────────────────────────────────────────


def derive_state(
    descriptor: StackDescriptor,
    info: ComponentInfo,  # type: ignore[name-defined]  # noqa: F821 — string annotation with `from __future__ import annotations`
) -> StackState:
    """Compare observed *info* against *descriptor* constraints.

    Pure function — no side effects, no I/O.  Maps factual
    ``ComponentInfo`` (what *is*) against declared ``StackDescriptor``
    (what *should be*) to produce the appropriate :class:`StackState`.

    Args:
        descriptor: The component's static descriptor.
        info:       Observed information from ``StackComponent.detect()``.

    Returns:
        ``NOT_INSTALLED``, ``INSTALLED``, ``OUTDATED``, or
        ``UNSUPPORTED``.
    """
    if not info.installed:
        return StackState.NOT_INSTALLED

    observed = _parse_version(info.version)
    if observed is None:
        return StackState.NOT_INSTALLED

    min_ver = _parse_version(descriptor.min_version)
    max_ver = _parse_version(descriptor.max_version)

    if min_ver is not None and observed < min_ver:
        return StackState.OUTDATED

    if max_ver is not None and observed > max_ver:
        return StackState.UNSUPPORTED

    return StackState.INSTALLED
