"""StackManager — lifecycle orchestrator for stack components.

Handles dependency resolution, state transitions, and event emission
for install/uninstall/verify/activate/deactivate operations.

Design: Core Stack Installation & Lifecycle — StackManager
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from apoch.stack import events as ev
from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.exceptions import StackNotFoundError
from apoch.stack.registry import StackRegistry
from apoch.stack.result import OperationResult
from apoch.stack.state import StackState, derive_state

log = logging.getLogger(__name__)


@dataclass
class ComponentStatus:
    """Runtime status of a managed component."""

    descriptor: StackDescriptor
    state: StackState = StackState.UNKNOWN
    info: ComponentInfo | None = None


class StackManager:
    """Creates, tracks, and orchestrates stack component lifecycles.

    Args:
        registry:   The ``StackRegistry`` containing component descriptors.
        emit_event: Optional callback for lifecycle events. Receives
                    ``(event_type, component_name, details_dict)``.
    """

    def __init__(
        self,
        registry: StackRegistry,
        *,
        emit_event: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._registry = registry
        self._emit_event = emit_event or (lambda _event, _comp, _details: None)
        self._instances: dict[str, StackComponent] = {}
        self._statuses: dict[str, ComponentStatus] = {}

        # Pre-populate statuses from registry
        for desc in self._registry.list():
            self._statuses[desc.name] = ComponentStatus(descriptor=desc)

    # ── Public API ───────────────────────────────────────────────────

    def register_instance(self, name: str, component: StackComponent) -> None:
        """Register a pre-created component instance.

        This bypasses entry-point loading, useful for testing or when
        instances are managed externally.
        """
        self._instances[name] = component
        if name not in self._statuses:
            desc = component.descriptor
            self._statuses[name] = ComponentStatus(descriptor=desc)
        log.info("Component instance registered", extra={"component": name})

    def get_status(self, component_name: str) -> ComponentStatus:
        """Return the current status of a component.

        Raises:
            StackNotFoundError: If the component is not registered.
        """
        try:
            return self._statuses[component_name]
        except KeyError:
            msg = f"Stack component '{component_name}' is not registered"
            log.warning("Component not found", extra={"component": component_name})
            raise StackNotFoundError(msg) from None

    def list_components(self) -> dict[str, ComponentStatus]:
        """Return a snapshot of every known component and its status."""
        return dict(self._statuses)

    async def refresh(self, component_name: str | None = None) -> None:
        """Re-detect every registered component (or a single one if named).

        Iterates all registered components, calls ``detect()`` on each,
        derives the new state, and stores both the derived state and the
        observed ``ComponentInfo`` on the status object.

        Resilient: if a single component's ``detect()`` raises, its
        state becomes ``ERROR`` and the method continues to the next
        component.
        """
        names = [component_name] if component_name else list(self._statuses)

        for name in names:
            status = self._statuses.get(name)
            if status is None:
                continue

            try:
                component = self._get_component(name)
                info = await component.detect()
            except Exception as exc:  # noqa: BLE001
                self._statuses[name].state = StackState.ERROR
                info = ComponentInfo(
                    installed=False,
                    metadata={"error": str(exc)},
                )

            ts = datetime.now().astimezone().isoformat()
            info = replace(info, detected_at=ts)

            if self._statuses[name].state is not StackState.ERROR:
                derived = derive_state(status.descriptor, info)
                self._statuses[name].state = derived

            self._statuses[name].info = info

    def refresh_sync(self, component_name: str | None = None) -> None:
        """Synchronous wrapper around :meth:`refresh`.

        Encapsulates the async boundary so future synchronous callers
        (CLI, TUI, scripts) don't need to manage the event loop.
        """
        asyncio.run(self.refresh(component_name))

    async def install(self, component_name: str) -> OperationResult:
        """Install a component and its dependencies.

        Returns:
            An ``OperationResult`` indicating success or failure.
        """
        status = self._get_status_or_raise(component_name)
        desc = status.descriptor

        # Idempotent — already installed
        if status.state in (StackState.INSTALLED, StackState.ACTIVE, StackState.INACTIVE):
            log.info(
                "Install skipped — already installed",
                extra={"component": component_name, "state": status.state.value},
            )
            return OperationResult(
                success=True,
                component=component_name,
                message=f"'{component_name}' is already installed (state={status.state})",
            )

        # Check dependencies
        for dep in desc.dependencies:
            dep_status = self._statuses.get(dep)
            if dep_status is None or dep_status.state not in (
                StackState.INSTALLED,
                StackState.ACTIVE,
                StackState.INACTIVE,
            ):
                log.warning(
                    "Install blocked — dependency not installed",
                    extra={"component": component_name, "dependency": dep},
                )
                return OperationResult(
                    success=False,
                    component=component_name,
                    message=f"Dependency '{dep}' is not installed",
                    details={"dependency": dep, "component": component_name},
                )

        log.info("Install starting", extra={"component": component_name})
        self._emit_event(ev.COMPONENT_INSTALLING, component_name, {"state": "installing"})
        self._statuses[component_name].state = StackState.INSTALLING

        # Execute install
        component = self._get_component(component_name)
        try:
            result = await component.install()
        except Exception as exc:  # noqa: BLE001
            self._statuses[component_name].state = StackState.ERROR
            self._emit_event(
                ev.COMPONENT_ERROR,
                component_name,
                {"error": str(exc), "state": "error"},
            )
            log.error(
                "Install failed with exception",
                extra={"component": component_name, "error": str(exc)},
            )
            return OperationResult(
                success=False,
                component=component_name,
                message=f"Installation failed: {exc}",
            )

        if result.success:
            self._statuses[component_name].state = StackState.INSTALLED
            self._emit_event(
                ev.COMPONENT_INSTALLED,
                component_name,
                {"state": "installed", **result.details},
            )
            log.info("Install succeeded", extra={"component": component_name})
        else:
            self._statuses[component_name].state = StackState.ERROR
            self._emit_event(
                ev.COMPONENT_ERROR,
                component_name,
                {"state": "error", "message": result.message},
            )
            log.error(
                "Install failed — component returned failure",
                extra={"component": component_name, "detail": result.message},
            )

        return result

    async def uninstall(self, component_name: str) -> OperationResult:
        """Uninstall a component.

        If the component is not installed it is a no-op (success).
        """
        status = self._get_status_or_raise(component_name)

        # No-op if not installed
        if status.state in (StackState.UNKNOWN, StackState.NOT_INSTALLED):
            log.info(
                "Uninstall skipped — was not installed",
                extra={"component": component_name},
            )
            return OperationResult(
                success=True,
                component=component_name,
                message=f"'{component_name}' was not installed",
            )

        # Check no other installed component depends on this one
        for other_name, other_status in self._statuses.items():
            if other_name == component_name:
                continue
            if other_status.state in (
                StackState.INSTALLED,
                StackState.ACTIVE,
                StackState.INACTIVE,
            ):
                if component_name in other_status.descriptor.dependencies:
                    log.warning(
                        "Uninstall blocked — required by another component",
                        extra={
                            "component": component_name,
                            "required_by": other_name,
                        },
                    )
                    return OperationResult(
                        success=False,
                        component=component_name,
                        message=f"'{component_name}' is required by '{other_name}'",
                    )

        log.info("Uninstall starting", extra={"component": component_name})
        self._emit_event(ev.COMPONENT_UNINSTALLING, component_name, {"state": "uninstalling"})

        component = self._get_component(component_name)
        try:
            result = await component.uninstall()
        except Exception as exc:  # noqa: BLE001
            self._emit_event(
                ev.COMPONENT_ERROR,
                component_name,
                {"error": str(exc)},
            )
            log.error(
                "Uninstall failed with exception",
                extra={"component": component_name, "error": str(exc)},
            )
            return OperationResult(
                success=False,
                component=component_name,
                message=f"Uninstall failed: {exc}",
            )

        self._statuses[component_name].state = StackState.NOT_INSTALLED
        self._emit_event(
            ev.COMPONENT_UNINSTALLED,
            component_name,
            {"state": "not_installed", **result.details},
        )
        log.info("Uninstall succeeded", extra={"component": component_name})
        return result

    async def verify(self, component_name: str, *, skip_async: bool = False) -> OperationResult:
        """Verify a component's installation.

        Two-phase check:
          1. Call ``detect()`` to observe the local installation.
          2. Derive state by comparing observed info against the
             descriptor's version constraints.
          3. If still relevant, run the component's own verify logic.

        Args:
            component_name: Name of the component to verify.
            skip_async:     Skip long-running checks (e.g. live API pings).
        """
        status = self._get_status_or_raise(component_name)
        descriptor = status.descriptor
        log.info("Verify starting", extra={"component": component_name, "skip_async": skip_async})
        self._emit_event(ev.COMPONENT_VERIFYING, component_name, {})

        component = self._get_component(component_name)

        # Phase 1 — detect reality
        info = await component.detect()
        derived = derive_state(descriptor, info)
        self._statuses[component_name].state = derived
        self._statuses[component_name].info = info

        # Phase 2 — early exit if not installed
        if derived is StackState.NOT_INSTALLED:
            self._emit_event(
                ev.COMPONENT_VERIFIED,
                component_name,
                {"success": False, "state": derived.value},
            )
            log.info("Verify — component not installed", extra={"component": component_name})
            return OperationResult(
                success=False,
                component=component_name,
                message=f"'{component_name}' is not installed",
            )

        # Phase 3 — run the component's own verification logic
        result = await component.verify(skip_async=skip_async)

        if not result.success:
            self._statuses[component_name].state = StackState.BROKEN
            log.error(
                "Verify failed — component is BROKEN",
                extra={"component": component_name, "detail": result.message},
            )

        self._emit_event(
            ev.COMPONENT_VERIFIED,
            component_name,
            {"success": result.success, "state": derived.value, **result.details},
        )
        if result.success:
            log.info("Verify succeeded", extra={"component": component_name})
        else:
            log.error(
                "Verify failed",
                extra={"component": component_name, "detail": result.message},
            )
        return result

    async def install_all(self) -> list[OperationResult]:
        """Install every registered component in registration order.

        Skips already-installed components (idempotent).  If any
        component fails, the method rolls back every previously
        installed component in reverse order before returning.

        Returns:
            A list of ``OperationResult``, one per component in the
            order they were processed.
        """
        results: list[OperationResult] = []
        installed: list[str] = []

        for name in self._statuses:
            result = await self.install(name)
            results.append(result)
            if result.success:
                installed.append(name)
            else:
                # Roll back in reverse order
                for installed_name in reversed(installed):
                    await self.uninstall(installed_name)
                break

        return results

    async def uninstall_all(self) -> list[OperationResult]:
        """Uninstall every registered component in reverse registration order.

        Components are processed in reverse order of their registration
        (dependents before dependencies).  Already-removed or
        non-installed components are skipped (idempotent).

        Returns:
            A list of ``OperationResult``, one per component in the
            order they were processed.
        """
        results: list[OperationResult] = []

        for name in reversed(list(self._statuses)):
            result = await self.uninstall(name)
            results.append(result)

        return results

    # ── Internals ────────────────────────────────────────────────────

    def _get_status_or_raise(self, name: str) -> ComponentStatus:
        try:
            return self._statuses[name]
        except KeyError:
            msg = f"Stack component '{name}' is not registered"
            log.warning("Component not found", extra={"component": name})
            raise StackNotFoundError(msg) from None

    def _get_component(self, name: str) -> StackComponent:
        """Return a component instance, loading from entry point if needed."""
        if name in self._instances:
            return self._instances[name]

        desc = self._registry.get(name)
        from importlib import import_module

        module_path, _, class_name = desc.entry_point.partition(":")
        module = import_module(module_path)
        cls = getattr(module, class_name)
        instance: StackComponent = cls()
        self._instances[name] = instance
        return instance
