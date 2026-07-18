"""Module ABC, state machine, and core types.

Spec: module-system §Public Interfaces, §Lifecycle Contract
Design: Interfaces / Contracts (Module ABC, ModuleMetadata, ModuleState, Context)
"""

from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from apoch.core.exceptions import LifecycleError, StateTransitionError

if TYPE_CHECKING:
    from apoch.core.events import EventBus
    from apoch.core.registry import ModuleRegistry

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------


class ModuleState(StrEnum):
    """Lifecycle states for an Apoch-AI module.

    Valid transitions (enforced by ``_StateMachine._transition``):

    * ``LOADED → RUNNING`` (via ``start()``)
    * ``RUNNING → STOPPED`` (via ``stop()``)
    * ``STOPPED → SHUTDOWN`` (via ``shutdown()``)
    * Any → ``FAILED`` (via exception boundary)
    """

    LOADED = "LOADED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    SHUTDOWN = "SHUTDOWN"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModuleMetadata:
    """Immutable metadata describing a module or plugin.

    Fields are designed for third-party plugins — even though only first-party
    modules exist in v1, the interface accommodates external packages.
    """

    name: str
    version: str
    description: str
    entry_point: str


@dataclass
class Context:
    """Execution context passed to ``Module.start()``.

    Carries cross-module service references and runtime infrastructure
    that modules may need while still keeping Core dependency-free of
    specific module implementations.

    ``services`` is populated by :class:`ModuleRegistry` before the
    first ``start()`` call — it is immutable at runtime.

    ``registry`` is set by :class:`Engine` and provides read-only
    access to all loaded modules for state/config introspection.
    """

    services: dict[str, Callable] = field(default_factory=dict)
    """Generic cross-module service registry.

    Populated once at startup by ``Registry.start_all()``.  Modules
    publish services via a ``@property services`` duck-typed attribute.
    Never modified at runtime.
    """

    registry: ModuleRegistry | None = None
    """Read-only reference to the ModuleRegistry for state queries.

    Set by ``Engine.start()`` before ``start_all()``.  ``None`` if
    the Engine has not started yet or has been stopped.
    """

    event_bus: EventBus | None = None
    """Reference to the Engine's EventBus for subscribing to system events.

    Set by ``Engine.start()`` before ``start_all()``.  ``None`` if
    the Engine has not started yet or has been stopped.
    """


# ---------------------------------------------------------------------------
# Lifecycle validation helpers
# ---------------------------------------------------------------------------


def _validate_lifecycle(method_name: str) -> Any:
    """Decorate a subclass lifecycle method so validation runs first.

    The returned decorator wraps any async method so that
    ``self._pre_{method_name}()`` is called **before** the original
    method body executes.  This guarantees lifecycle checks always run,
    even when a subclass forgets to call ``super()``.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(self, *args, **kwargs):
            getattr(self, f"_pre_{method_name}")()
            return await fn(self, *args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# State machine mixin
# ---------------------------------------------------------------------------


class _StateMachine:
    """Internal state machine that validates module state transitions.

    Used as a mixin by :class:`Module`.  Exposes ``_transition()`` for
    controlled state changes and ``_state`` for read access.
    """

    _valid_transitions: ClassVar[dict[ModuleState, set[ModuleState]]] = {
        ModuleState.LOADED: {ModuleState.RUNNING, ModuleState.FAILED},
        ModuleState.RUNNING: {ModuleState.STOPPED, ModuleState.FAILED},
        ModuleState.STOPPED: {ModuleState.SHUTDOWN, ModuleState.FAILED},
    }

    def __init__(self) -> None:
        self._state: ModuleState = ModuleState.LOADED

    def _transition(self, target: ModuleState) -> None:
        """Transition to *target* state.

        Raises :exc:`StateTransitionError` if the transition is not
        registered in the valid-transitions table.
        """
        allowed = self._valid_transitions.get(self._state)
        if allowed is None or target not in allowed:
            raise StateTransitionError(
                f"Invalid state transition: {self._state.value} → {target.value}"
            )
        self._state = target


# ---------------------------------------------------------------------------
# Module ABC
# ---------------------------------------------------------------------------


class Module(ABC, _StateMachine):
    """Abstract base class for every Apoch-AI module (and plugin).

    Subclasses **must** implement the three async lifecycle methods:
    ``start()``, ``stop()``, ``shutdown()``.  Lifecycle validation is
    automatically injected via ``__init_subclass__`` — subclasses do
    NOT need to call ``super()`` in these methods.

    Usage::

        class MyModule(Module):
            async def start(self, context: Context) -> None:
                # ... module-specific startup

            async def stop(self) -> None:
                # ... module-specific teardown

            async def shutdown(self) -> None:
                # ... module-specific cleanup
    """

    # Set of method names that every concrete module must implement.
    _REQUIRED: ClassVar[frozenset] = frozenset({"start", "stop", "shutdown"})
    # Populated by ``__init_subclass__`` when methods are missing.
    _missing_methods: ClassVar[frozenset] = frozenset()

    # ------------------------------------------------------------------
    # Metaclass-like enforcement via __init_subclass__
    # ------------------------------------------------------------------

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register and wrap subclass lifecycle methods.

        * Raises ``TypeError`` at instantiation time for missing methods.
        * Injects ``_pre_*`` validation before each method via
          :func:`_validate_lifecycle`.
        """
        super().__init_subclass__(**kwargs)

        # Record which (if any) required methods are missing.
        missing = cls._REQUIRED - set(cls.__dict__)
        cls._missing_methods = missing

        # Wrap each present lifecycle method with validation.
        for name in cls._REQUIRED:
            if name in cls.__dict__:
                original = cls.__dict__[name]
                setattr(cls, name, _validate_lifecycle(name)(original))

    # ------------------------------------------------------------------
    # Lifecycle validation hooks (called by the wrapper)
    # ------------------------------------------------------------------

    def _pre_start(self) -> None:
        """Validate pre-conditions before running the subclass ``start()``."""
        if self._state == ModuleState.SHUTDOWN:
            raise LifecycleError("Cannot start a module that has been shut down")
        if self._state == ModuleState.FAILED:
            raise LifecycleError("Cannot start a module that has failed")
        self._transition(ModuleState.RUNNING)

    def _pre_stop(self) -> None:
        """Validate pre-conditions before running the subclass ``stop()``."""
        if self._state != ModuleState.RUNNING:
            raise LifecycleError(f"Cannot stop module from state {self._state.value}")
        self._transition(ModuleState.STOPPED)

    def _pre_shutdown(self) -> None:
        """Validate pre-conditions before running the subclass ``shutdown()``."""
        if self._state != ModuleState.STOPPED:
            raise LifecycleError(f"Cannot shut down module from state {self._state.value}")
        self._transition(ModuleState.SHUTDOWN)

    # ------------------------------------------------------------------
    # Public lifecycle API  (abstract — subclasses MUST override)
    # ------------------------------------------------------------------

    def __init__(self, config: dict) -> None:
        """Initialise the module with *config*.

        Sets the initial state to :attr:`ModuleState.LOADED`.
        """
        if self._missing_methods:
            raise TypeError(
                f"Can't instantiate abstract class {self.__class__.__name__} "
                f"without methods: {', '.join(sorted(self._missing_methods))}"
            )
        _StateMachine.__init__(self)
        self._config: dict = config

    @property
    def state(self) -> ModuleState:
        """Current lifecycle state of this module."""
        return self._state

    @abstractmethod
    async def start(self, context: Context) -> None:
        """Start the module.

        Transitions ``LOADED → RUNNING``.  Subclasses **must** override
        this method.
        """
        # The abstract-method body provides a fallback for direct callers
        # that bypass subclass override (should not happen in practice).
        self._pre_start()

    @abstractmethod
    async def stop(self) -> None:
        """Stop the module.

        Transitions ``RUNNING → STOPPED``.  Subclasses **must** override
        this method.
        """
        self._pre_stop()

    @abstractmethod
    async def shutdown(self) -> None:
        """Shut down the module.

        Transitions ``STOPPED → SHUTDOWN``.  Subclasses **must** override
        this method.
        """
        self._pre_shutdown()
