# Design: PR3C — Vision Module

## Objective

Observability module — structured NDJSON logging with rotation, MCP-exposed module state/config/logs/system introspection, and optional Chronicle event archival via duck-typed service injection.

## Design Constraints (from Proposal approval)

1. `Context.services` is completely generic — no assumptions about Chronicle, Vision, or any future module.
2. Service key `"chronicle.record"` is a documented public contract. Stable, not dynamically generated.
3. Missing service is never an error — Vision degrades gracefully.
4. Registry only discovers and collects services; it never executes or interprets them.
5. No singletons, no global state — everything travels through Context.
6. The services dict is the first inter-module communication API. Future modules (Analytics, Notifications) will use the same mechanism.

### Additional Constraints (from Design approval)

7. **Context.services is immutable at runtime.** It is populated once during `Registry.start_all()` before any module's `start()` runs. After that, services are read-only. No module adds or removes services at runtime.
8. **Service key collisions are fatal.** If two modules publish the same service key, `Registry` MUST detect the collision and raise an error (or at minimum log CRITICAL). Silent overwrite is never acceptable.
9. **Each published service is a documented contract.** Every service must specify: stable name, callable signature (parameters + return type), and documented behaviour when the service is unavailable. This enables future module authors to depend on services without inspecting implementation code.

## Architecture

```
                    ┌─────────────────────┐
                    │     Context          │
                    │  ┌───────────────┐   │
                    │  │ services:     │   │
                    │  │ dict[str,     │   │
 Engine ──set──►    │  │   Callable]   │   │
                    │  │               │   │
                    │  │ registry:     │   │
                    │  │ ModuleRegistry│   │
                    │  └───────────────┘   │
                    └─────────┬───────────┘
                              │ (passed to start())
                              ▼
     ┌─────────────────────────────────────────┐
     │              VisionModule                │
     │  ┌─────────────────────────────────┐    │
     │  │ start(context):                 │    │
     │  │  event_sink = context.services  │    │
     │  │    .get("chronicle.record")     │    │
     │  │  registry = context.registry    │    │
     │  │  init log_dir, handler, buffer  │    │
     │  └─────────────────────────────────┘    │
     │                                         │
     │  log(level, msg, module, **ctx) ──►     │
     │    ├── NDJSON → RotatingFileHandler     │
     │    ├── append to ring buffer            │
     │    └── if event_sink: await event_sink  │
     │                   (→ Chronicle)         │
     │                                         │
     │  recent(limit, level) → list[LogRecord] │
     │  module_state(name?) → dict             │
     │  module_config(name?) → dict            │
     │  system_info() → SystemInfo             │
     │                                         │
     │  get_tool_defs() → list[ToolDef]        │
     └─────────────────────────────────────────┘
```

## Interfaces / Contracts

### Context changes (core/module.py)

```python
@dataclass
class Context:
    """Execution context passed to Module.start().

    Extended in PR3C with generic cross-module service discovery
    and registry reference for state/config introspection.
    """

    services: dict[str, Callable] = field(default_factory=dict)
    """Generic service registry for inter-module communication.

    Modules publish services via ``@property services`` returning
    ``dict[str, Callable]``. The Registry collects them into this
    dict before calling ``start()`` on any module.

    Key convention: ``{module_name}.{method_name}``, e.g.
    ``"chronicle.record"``, ``"guardian.protect"``.
    """

    registry: ModuleRegistry | None = None
    """Reference to the ModuleRegistry for state/config queries.

    Set by Engine before start_all(). Modules read this to
    inspect other loaded modules *without* importing them.
    Modules MUST treat this as read-only.
    """
```

Uses `TYPE_CHECKING` import to avoid circular dep (module.py → registry.py → module.py).

### Registry changes (core/registry.py)

```python
async def start_all(self, context: Context) -> None:
    # --- NEW: Generic service gathering (PR3C) ---
    # Duck-typed: any loaded module can expose services.
    # Registry discovers and collects — never executes.
    for mod in self._loaded.values():
        svc = getattr(mod, "services", None)
        if isinstance(svc, dict):
            for key in svc:
                if key in context.services:
                    # Collision — two modules claim the same key
                    logger.critical(
                        "Service key '%s' collision. "
                        "Module '%s' attempted to register %s, "
                        "but key is already registered.",
                        key, type(mod).__module__, key,
                    )
                    raise ModuleLoadError(
                        f"Service key collision: '{key}' is already registered. "
                        f"Cannot register from {type(mod).__module__}."
                    )
            context.services.update(svc)

    # --- Existing lifecycle loop ---
    for name in self._init_order:
        # ... unchanged
```

Service collisions raise `ModuleLoadError` — fail fast, never silent overwrite. This is the ONLY Registry change. No module names, no service semantics.

### Engine changes (core/engine.py)

```python
# Inside Engine.start(), after loading modules:
self._context = Context()
self._context.registry = self._registry   # ← NEW: one line
await self._registry.start_all(self._context)
```

### Chronicle changes (modules/chronicle/module.py)

```python
@property
def services(self) -> dict[str, Callable]:
    """Publish the event-recording API as a cross-module service."""
    return {"chronicle.record": self.record}
```

Chronicle continues to expose its full public API (`record()`, `query()`, `prune()`, `stats()`). The `services` property only exposes `record`, which is all Vision needs.

### Vision data types (modules/vision/models.py)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LogRecord:
    """A single structured log entry."""
    timestamp: datetime
    level: str                  # DEBUG | INFO | WARN | ERROR | FATAL
    message: str
    module: str | None
    context: dict[str, Any] = field(default_factory=dict)
    pid: int


@dataclass
class SystemInfo:
    """Process and environment snapshot."""
    python_version: str
    platform: str
    pid: int
    uptime_seconds: float
    memory_rss_mb: float | None    # None on non-Linux


__all__ = ["LogRecord", "SystemInfo"]
```

### VisionModule (modules/vision/module.py)

```python
class VisionModule(Module):
    """Vision — structured logging and MCP-observable introspection.

    Config keys:
        log_dir (str):         Log directory path (default: ~/.local/share/apoch/logs/).
        log_file (str):        Log file name (default: "vision.ndjson").
        max_bytes (int):       Max log file size before rotation (default: 1_048_576).
        backup_count (int):    Max rotated backup files (default: 3).
        buffer_size (int):     In-memory ring buffer capacity (default: 1000).
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._log_dir: Path = ...
        self._max_bytes: int = ...
        self._backup_count: int = ...
        self._buffer_size: int = ...
        self._buffer: deque[LogRecord] = deque(maxlen=buffer_size)
        self._handler: logging.handlers.RotatingFileHandler | None = None
        self._event_sink: Callable | None = None
        self._registry: ModuleRegistry | None = None
        self._started_at: float = 0.0

    # --- Lifecycle ---

    async def start(self, context: Context) -> None:
        """Initialise log directory, handler, and capture injected services."""
        self._event_sink = context.services.get("chronicle.record")
        self._registry = context.registry
        self._started_at = time.monotonic()
        # Create log directory, init RotatingFileHandler with JSON formatter
        # If log_dir unwritable → log warning, continue degraded (no file)

    async def stop(self) -> None:
        """Flush and close the log handler."""
        if self._handler is not None:
            self._handler.close()
            self._handler = None

    async def shutdown(self) -> None:
        """No-op after stop()."""

    # --- Logging API ---

    def log(self, level: str, message: str, *, module: str | None = None, **kw: Any) -> None:
        """Record a structured log entry.

        FAILSAFE BEHAVIOUR for production robustness:

        1. JSON serialization failure for context → skip the problematic
           key, log warning, other context keys preserved.
        2. Log directory not writable at rotation time → log to stderr,
           Vision continues degraded.
        3. event_sink callable raises → log warning, event archival
           silently dropped for this entry.
        """
        record = LogRecord(
            timestamp=datetime.now(UTC),
            level=level.upper(),
            message=message,
            module=module,
            context=kw,
            pid=os.getpid(),
        )
        # In-memory buffer (bounded ring)
        self._buffer.append(record)

        # Rotating JSON file
        if self._handler is not None:
            line = self._format_json(record)
            self._handler.emit(...)  # via stdlib logging

        # Optional Chronicle archival
        if self._event_sink is not None:
            try:
                # Convert LogRecord → ActivityEvent (duck-typed callable)
                ...
                await self._event_sink(event)
            except Exception:
                logger.warning(...)  # never crash Vision

    # --- Query API ---

    async def recent(self, limit: int = 50, level: str | None = None) -> list[LogRecord]:
        """Return recent log entries from the ring buffer, newest first."""
        ...

    # --- MCP tool handlers (called by adapter) ---

    async def module_state(self, name: str | None = None) -> dict:
        """Return current state for all modules, or a single module.

        Uses context.registry.loaded to iterate modules. No module imports.
        """
        if self._registry is None:
            return {}
        modules = self._registry.loaded
        if name is not None:
            mod = modules.get(name)
            if mod is None:
                return {"not_found": True}
            return {name: mod.state.value}
        return {n: m.state.value for n, m in modules.items()}

    async def module_config(self, name: str | None = None) -> dict:
        """Return effective config for a module (via registry).

        Not found → return {name: not_found: True}.
        No registry → return {}.
        """
        ...

    async def system_info(self) -> SystemInfo:
        """Return process health snapshot.

        pid: os.getpid()
        python_version: platform.python_version()
        platform: platform.platform()
        uptime_seconds: time.monotonic() - self._started_at
        memory_rss_mb: Reads /proc/self/status (Linux) or returns None
        """
        ...

    def get_tool_defs(self) -> list[ToolDef]:
        """Return MCP tool definitions for this module.

        Registration with the adapter is handled externally.
        """
        return [
            ToolDef(name="vision_state", description="...", input_schema={...}),
            ToolDef(name="vision_config", description="...", input_schema={...}),
            ToolDef(name="vision_logs", description="...", input_schema={...}),
            ToolDef(name="vision_system", description="...", input_schema={...}),
        ]
```

### Module init (modules/vision/__init__.py)

Same lazy-export pattern as Chronicle and Guardian:

```python
def __getattr__(name: str) -> Any:
    if name == "VisionModule":
        from apoch.modules.vision.module import VisionModule
        return VisionModule
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

__all__ = ["VisionModule"]
```

### Entry point

```toml
[project.entry-points."apoch.modules"]
vision = "apoch.modules.vision.module:VisionModule"
```

## Core Changes Summary

| File | Change | Rationale |
|------|--------|-----------|
| `core/module.py` | Context: +`services` + `registry` fields | Generic, no module names |
| `core/registry.py` | start_all: + service gathering loop | Duck-typed, doesn't execute services |
| `core/engine.py` | start: + `context.registry = self._registry` | One line, generic |

All three changes are module-agnostic. Zero module names appear in Core code.

## Error Handling

| Condition | Behaviour |
|-----------|-----------|
| Log directory not writable | Log warning; Vision continues without file logging |
| JSON serialization failure for context | Skip the problematic key; log warning; other keys preserved |
| Log rotation fails (disk full) | Log warning; continue with single file |
| event_sink raises | Log warning; this entry not archived; Vision continues |
| Registry is None | `module_state()` and `module_config()` return empty dict |
| Unknown module queried in `module_state()` | Return `{name: {"not_found": true}}` |
| Memory info unavailable (non-Linux) | `memory_rss_mb: None` |

## Testing Strategy

### Unit tests (~200 lines)

| Test scope | What to test |
|-----------|-------------|
| `LogRecord` creation | Timestamp, level, message, context, pid |
| `log()` → buffer | Entry appears in `recent()` |
| `log()` → file | NDJSON line written to log file |
| `log()` with context | JSON context serialized correctly |
| `log()` FATAL → immediate flush | Entry on disk immediately |
| `recent()` filtering | Level filter, limit, no args |
| `recent()` with empty buffer | Returns empty list |
| `module_state()` | States from mock registry |
| `module_state("unknown")` | Returns not_found dict |
| `module_config()` | Config from mock registry |
| `system_info()` | PID matches os.getpid(), platform not empty |
| `system_info()` memory on non-Linux | memory_rss_mb is None |
| `get_tool_defs()` | Returns 4 ToolDef entries |
| Degraded mode — no registry | module_state returns empty dict |
| Degraded mode — no event_sink | log() works without Chronicle |
| Lifecycle | LOADED→RUNNING→STOPPED→SHUTDOWN |

### Integration tests

- Vision + Chronicle: Verify event_sink pushes ActivityEvent to Chronicle
- Vision + Registry: Verify module_state returns correct states
- Clean install from clone: Vision entry point resolves

## Chronicle Integration — Service Contract

| Field | Value |
|-------|-------|
| **Service key** | `"chronicle.record"` |
| **Type** | `Callable[[ActivityEvent], Awaitable[None]]` |
| **Module** | ChronicleModule |
| **Exposed via** | `@property services` |
| **Discovery** | Registry collects into `context.services` |
| **Optional** | YES — Vision works without it |
| **Future** | Same pattern for Guardian (`guardian.protect`), future modules |

The service key is a documented, stable contract. All future modules that want to expose callable services use the same `@property services` pattern.

## Module __init__ files

```python
# src/apoch/modules/vision/__init__.py
"""Vision — structured logging and MCP-observable introspection.

Spec: module-vision
Design: PR3C — Vision Module
"""

from __future__ import annotations
from typing import Any

__all__ = ["VisionModule"]


def __getattr__(name: str) -> Any:
    """Lazy-export VisionModule to avoid circular imports."""
    if name == "VisionModule":
        from apoch.modules.vision.module import VisionModule  # noqa: PLC0415
        return VisionModule
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
```

## Files to Create

| File | Lines |
|------|-------|
| `src/apoch/modules/vision/__init__.py` | ~20 |
| `src/apoch/modules/vision/module.py` | ~220 |
| `src/apoch/modules/vision/models.py` | ~40 |
| `tests/modules/vision/__init__.py` | empty |
| `tests/modules/vision/test_vision.py` | ~200 |

Total: ~480 lines, 4 new files, 3 core modifications (< 10 LOC each, all generic).

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Context circular import (module.py ↔ registry.py) | `TYPE_CHECKING` guard — runtime zero-cost |
| service gathering adds latency | Module count is < 10; dict update is O(n) |
| `/proc/self/status` Linux-only | Graceful None fallback |
| Vision.log() is synchronous but event_sink is async | Fire-and-forget via `asyncio.ensure_future` or task group |
| MCP tools not registered end-to-end | Same pattern as PR3A/PR3B — test APIs directly, defer MCP transport wiring |
