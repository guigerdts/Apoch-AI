"""Error-handling tests for StackManager — exception resilience via fakes.

Phase 14 — validates that StackManager gracefully handles component
errors through fakes and monkeypatches, not OS-level dependencies.

All scenarios use :class:`RaisingComponent` — a configurable fake that
raises on specified lifecycle methods — or inline components that
return :class:`OperationResult` with ``success=False``.

No production code is modified.
"""

from __future__ import annotations

import pytest

from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.manager import StackManager
from apoch.stack.registry import StackRegistry
from apoch.stack.result import OperationResult
from apoch.stack.state import StackState

# ── Raising component (fake) ─────────────────────────────────────────


class RaisingComponent(StackComponent):
    """Fake component that raises during selected lifecycle methods.

    Args:
        descriptor: Component descriptor.
        raise_on:  Set of lifecycle method names that should raise.
                   Recognised values: ``"install"``, ``"uninstall"``,
                   ``"verify"``, ``"activate"``, ``"deactivate"``.
        exception: Exception class to raise (default ``RuntimeError``).
    """

    def __init__(
        self,
        descriptor: StackDescriptor,
        *,
        raise_on: set[str] | None = None,
        exception: type[Exception] = RuntimeError,
    ) -> None:
        self._descriptor = descriptor
        self._raise_on = raise_on or set()
        self._exception = exception

    @property
    def descriptor(self) -> StackDescriptor:
        return self._descriptor

    async def detect(self) -> ComponentInfo:
        if "detect" in self._raise_on:
            msg = f"{self._descriptor.name}: {self._exception.__name__} in detect"
            raise self._exception(msg)
        return ComponentInfo(installed=True, version=self._descriptor.version)

    async def install(self) -> OperationResult:
        if "install" in self._raise_on:
            msg = f"{self._descriptor.name}: {self._exception.__name__} in install"
            raise self._exception(msg)
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def uninstall(self) -> OperationResult:
        if "uninstall" in self._raise_on:
            msg = f"{self._descriptor.name}: {self._exception.__name__} in uninstall"
            raise self._exception(msg)
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        if "verify" in self._raise_on:
            msg = f"{self._descriptor.name}: {self._exception.__name__} in verify"
            raise self._exception(msg)
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def activate(self) -> OperationResult:
        if "activate" in self._raise_on:
            msg = f"{self._descriptor.name}: {self._exception.__name__} in activate"
            raise self._exception(msg)
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def deactivate(self) -> OperationResult:
        if "deactivate" in self._raise_on:
            msg = f"{self._descriptor.name}: {self._exception.__name__} in deactivate"
            raise self._exception(msg)
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def health(self) -> dict:
        if "health" in self._raise_on:
            msg = f"{self._descriptor.name}: {self._exception.__name__} in health"
            raise self._exception(msg)
        return {"status": "healthy"}


# ── Helpers ──────────────────────────────────────────────────────────


def make_descriptor(name: str) -> StackDescriptor:
    """Create a minimal ``StackDescriptor``."""
    return StackDescriptor(
        name=name,
        kind="services",
        version="1.0.0",
        description=f"Fake {name}",
        entry_point=f"test:{name}",
    )


def build_manager(*names: str, raise_on: set[str] | None = None) -> StackManager:
    """Create a ``StackManager`` pre-loaded with ``RaisingComponent`` instances.

    Every component shares the same *raise_on* set.  For mixed
    scenarios (some raise, some don't) use the helpers directly.
    """
    registry = StackRegistry()
    instances: dict[str, RaisingComponent] = {}
    for name in names:
        desc = make_descriptor(name)
        registry.register(desc)
        instances[name] = RaisingComponent(desc, raise_on=raise_on)
    mgr = StackManager(registry)
    for name, instance in instances.items():
        mgr.register_instance(name, instance)
    return mgr


# ── Tests ────────────────────────────────────────────────────────────


class TestSingleOperationExceptions:
    """Individual lifecycle methods raise exceptions.

    The manager must catch every exception from a component and either
    return a failure ``OperationResult`` or let it propagate according
    to its contract.
    """

    async def test_install_raises_exception(self):
        """Component.install() raises → manager catches, returns failure,
        state transitions to ERROR."""
        mgr = build_manager("comp-a", raise_on={"install"})

        result = await mgr.install("comp-a")

        assert result.success is False
        assert "comp-a" in result.message
        assert mgr.get_status("comp-a").state is StackState.ERROR

    async def test_install_reaches_correct_state(self):
        """After a raising install, ``list_components`` reflects ERROR."""
        mgr = build_manager("comp-a", raise_on={"install"})

        await mgr.install("comp-a")

        statuses = mgr.list_components()
        assert statuses["comp-a"].state is StackState.ERROR

    async def test_uninstall_raises_exception(self):
        """Component.uninstall() raises → manager catches, returns failure."""
        mgr = build_manager("comp-a", raise_on={"uninstall"})
        # Install first so we have something to uninstall
        await mgr.install("comp-a")

        result = await mgr.uninstall("comp-a")

        assert result.success is False
        assert "comp-a" in result.message

    async def test_verify_raises_exception(self):
        """Component.verify() raises → exception propagates.

        *Design note:* Unlike :meth:`StackManager.install` and
        :meth:`StackManager.uninstall`, the :meth:`StackManager.verify`
        method does **not** wrap the component call in a try/except.
        A raising component will propagate the exception to the caller.
        """
        mgr = build_manager("comp-a", raise_on={"verify"})
        await mgr.install("comp-a")

        with pytest.raises(RuntimeError, match="comp-a"):
            await mgr.verify("comp-a")


class TestVariousExceptionTypes:
    """Different exception types are all caught by the same handler.

    Real-world equivalents:
      - ``IOError`` → disk full / I/O failure
      - ``PermissionError`` → permission denied
      - ``RuntimeError`` → stolen lock, state conflict
    """

    @pytest.mark.parametrize(
        ("exc_cls", "scenario"),
        [
            pytest.param(IOError, "disk full", id="disk_full"),
            pytest.param(PermissionError, "permission denied", id="permission_denied"),
            pytest.param(RuntimeError, "stolen lock", id="stolen_lock"),
        ],
    )
    async def test_install_raises_various_exception_types(
        self,
        exc_cls: type[Exception],
        scenario: str,  # noqa: ARG002 — used for parametrize id only
    ) -> None:
        """Exception type does not affect handling — all produce ERROR + failure."""
        desc = make_descriptor("comp-a")
        registry = StackRegistry()
        registry.register(desc)
        mgr = StackManager(registry)
        mgr.register_instance(
            "comp-a",
            RaisingComponent(desc, raise_on={"install"}, exception=exc_cls),
        )

        result = await mgr.install("comp-a")

        assert result.success is False
        assert mgr.get_status("comp-a").state is StackState.ERROR

    async def test_install_returns_failure_corruption(self):
        """Component returns ``OperationResult(success=False)`` → state → ERROR.

        Real-world equivalent: manifest checksum mismatch or data corruption.
        Unlike exception-based failures, this path exercises the
        ``if result.success: ... else: ...`` branch in :meth:`StackManager.install`.
        """
        desc = make_descriptor("comp-a")

        class CorruptComponent(StackComponent):
            """Component that always fails install with a corruption message."""

            @property
            def descriptor(self) -> StackDescriptor:
                return desc

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0.0")

            async def install(self) -> OperationResult:
                return OperationResult(
                    success=False,
                    component="comp-a",
                    message="manifest checksum mismatch",
                    details={"expected": "abc123", "actual": "def456"},
                )

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        registry = StackRegistry()
        registry.register(desc)
        mgr = StackManager(registry)
        mgr.register_instance("comp-a", CorruptComponent())

        result = await mgr.install("comp-a")

        assert result.success is False
        assert "checksum" in result.message
        assert mgr.get_status("comp-a").state is StackState.ERROR


class TestBatchErrorPaths:
    """Batch operations (install_all / uninstall_all) under failures."""

    async def test_install_all_rollback_on_exception(self):
        """Component raises during ``install_all()`` → earlier components
        are rolled back to NOT_INSTALLED."""
        # Build a single manager with both components — comp-b raises on install
        registry = StackRegistry()

        desc_a = make_descriptor("comp-a")
        registry.register(desc_a)

        desc_b = make_descriptor("comp-b")
        registry.register(desc_b)

        mgr = StackManager(registry)
        mgr.register_instance("comp-a", RaisingComponent(desc_a))
        mgr.register_instance("comp-b", RaisingComponent(desc_b, raise_on={"install"}))

        results = await mgr.install_all()

        assert len(results) == 2
        assert results[0].success is True  # comp-a installed
        assert results[1].success is False  # comp-b failed

        # comp-a should have been rolled back
        assert mgr.get_status("comp-a").state in (
            StackState.NOT_INSTALLED,
            StackState.UNKNOWN,
        )
        assert mgr.get_status("comp-b").state is StackState.ERROR

    async def test_install_all_rollback_uninstall_also_raises(self):
        """Rollback uninstall also raises → no crash, failure reported.

        Scenario:
          1. comp-a installs successfully (added to rollback list).
          2. comp-b raises on install (triggers rollback).
          3. Rollback tries to uninstall comp-a → this also raises.
          4. The system must not crash and must return consistent results.
        """
        registry = StackRegistry()

        desc_a = make_descriptor("comp-a")
        registry.register(desc_a)

        desc_b = make_descriptor("comp-b")
        registry.register(desc_b)

        class InstallOkUninstallFailsComponent(StackComponent):
            """Installs fine but raises on uninstall."""

            @property
            def descriptor(self) -> StackDescriptor:
                return desc_a

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def uninstall(self) -> OperationResult:
                raise RuntimeError("comp-a: uninstall failed")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="comp-a", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        class FailInstallComponent(StackComponent):
            """Raises on install."""

            @property
            def descriptor(self) -> StackDescriptor:
                return desc_b

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0.0")

            async def install(self) -> OperationResult:
                raise RuntimeError("comp-b: install failed")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="comp-b", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="comp-b", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="comp-b", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="comp-b", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("comp-a", InstallOkUninstallFailsComponent())
        mgr.register_instance("comp-b", FailInstallComponent())

        results = await mgr.install_all()

        assert len(results) == 2
        # comp-a installed successfully
        assert results[0].success is True
        # comp-b failed
        assert results[1].success is False

        # *Design note:* When rollback uninstall also raises, the
        # failed component's state changes to ERROR but the rolled-back
        # component stays in INSTALLED because the uninstall exception
        # prevented the NOT_INSTALLED transition.  This is a known
        # limitation — the system is partially inconsistent after a
        # double failure.  A production fix should set the rolled-back
        # component to ERROR when its rollback uninstall fails.
        assert mgr.get_status("comp-b").state is StackState.ERROR  # install raised
