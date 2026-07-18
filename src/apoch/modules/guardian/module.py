"""GuardianModule — exception isolation and diagnostics for Apoch-AI modules.

Spec: module-guardian §Exception Isolation, §State Machine
Design: PR3B — Guardian Module §Interfaces / Contracts
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any

from apoch.core.module import Context, Module, ModuleState
from apoch.modules.guardian.diagnostics import ModuleDiagnostics

logger = logging.getLogger(__name__)


def _make_empty_diag(module_name: str) -> ModuleDiagnostics:
    """Return a zeroed-out diagnostics entry for a fresh module."""
    return ModuleDiagnostics(
        module_name=module_name,
        current_state=ModuleState.LOADED.value,
        last_error=None,
        last_error_traceback=None,
        fail_count=0,
        last_failure_time=None,
    )


class GuardianModule(Module):
    """Guardian — exception boundaries and diagnostics for Apoch-AI modules.

    Wraps module lifecycle calls with try/except, captures structured
    diagnostics on failure, and transitions the failing module to
    ``FAILED`` state.  Guardian itself cannot protect its own lifecycle
    — the ``ModuleRegistry`` handles that with a raw try/except.

    Configuration (via ``config`` dict):
        (none currently — all defaults)
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._diagnostics: dict[str, ModuleDiagnostics] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, context: Context) -> None:  # noqa: ARG002
        """Initialise the diagnostics store.

        ``start()`` is lightweight — the diagnostics dict is already
        initialised in ``__init__``.
        """
        logger.info("Guardian started")

    async def stop(self) -> None:
        """Tear down the diagnostics store.

        Safe to call multiple times — in-memory dict is simply cleared.
        """
        self._diagnostics.clear()

    async def shutdown(self) -> None:
        """Final cleanup.  No-op after ``stop()``."""

    # ------------------------------------------------------------------
    # Exception boundary
    # ------------------------------------------------------------------

    async def protect(self, coro: Awaitable, module: Module) -> Any:
        """Execute *coro* inside an exception boundary.

        On success returns the coroutine result.
        On failure:
          - Captures ``ModuleDiagnostics`` (error type, message, traceback)
          - Increments ``fail_count``
          - Sets ``module._state`` to ``FAILED``
          - Returns ``None``

        ``CancelledError`` and ``KeyboardInterrupt`` are **never**
        swallowed — they always propagate.
        """
        try:
            return await coro
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            mod_name = module.__class__.__name__
            old = self._diagnostics.get(mod_name, _make_empty_diag(mod_name))
            diag = ModuleDiagnostics(
                module_name=module.__class__.__name__,
                current_state=ModuleState.FAILED.value,
                last_error=f"{type(exc).__name__}: {exc}",
                last_error_traceback=tb,
                fail_count=old.fail_count + 1,
                last_failure_time=datetime.now(UTC).isoformat(),
            )
            self._diagnostics[module.__class__.__name__] = diag
            module._state = ModuleState.FAILED  # type: ignore[attr-defined]
            logger.warning(
                "Guardian caught %s in %s: %s",
                type(exc).__name__,
                module.__class__.__name__,
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Diagnostics retrieval
    # ------------------------------------------------------------------

    def diagnostics(self, module_name: str) -> ModuleDiagnostics | None:
        """Return diagnostics for *module_name*, or ``None`` if clean."""
        return self._diagnostics.get(module_name)

    async def all_diagnostics(self) -> dict[str, ModuleDiagnostics]:
        """Return a snapshot of all tracked diagnostics."""
        return dict(self._diagnostics)

    def clear_diagnostics(self, module_name: str) -> None:
        """Remove diagnostics for a single module."""
        self._diagnostics.pop(module_name, None)

    def clear_all_diagnostics(self) -> None:
        """Remove all diagnostics entries."""
        self._diagnostics.clear()


__all__ = ["GuardianModule"]
