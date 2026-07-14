# Design: PR4 — MCP Adapter / Tool Runtime

## Technical Approach

Two-layer dispatch: (1) `AgentAdapterManager` bridges Registry → Adapter during startup, (2) `register_module_tools()` internalizes schema validation, handler resolution, and structured response formatting. Engine stays adapter-unaware.

## Architecture Decisions

### Decision: Discovery loop lives in AgentAdapterManager, not Engine

**Choice**: New `AgentAdapterManager` class in `apoch/adapters/manager.py` owns the discovery loop.
**Alternatives**: `Engine.start()` — rejected because Core must not import `adapters/*`.
**Rationale**: `Engine` is in `apoch/core/` — importing adapters violates the Core dependency rule. The manager bridges Registry + Adapter.

### Decision: Self-contained registration model

**Choice**: Adapter stores `dict[str, _ToolSlot]` where `_ToolSlot` = `{module, handler, schema}`.
**Rationale**: Adapter owns the runtime; FastMCP co-located state.

### Decision: Registration-time handler validation

**Choice**: `register_module_tools()` calls `getattr(module, handler_name)` and validates it's a public callable. On failure → `HANDLER_NOT_FOUND`, tool not registered.
**Rationale**: Catches config errors at startup, not on first tool call.

### Decision: Sync/async via inspect.isawaitable()

**Choice**: Check `inspect.isawaitable(result)` after calling the handler. Await if true, return directly if false.
**Rationale**: Zero boilerplate for module authors. No `is_async` flag needed.

## Data Flow

**Startup** (AgentAdapterManager):
```
adapter.start() → FastMCP up
engine.start() → modules loaded + started
for name in sorted(registry.loaded):
  defs = mod.get_tool_defs()         ← if hasattr
  validate each handler_name exists  ← early fail
  adapter.register_module_tools(name, defs)
```

**Dispatch** (per tool call):
```
FastMCP JSON-RPC → Adapter._dispatch(name, kwargs)
  → _tool_registry[name]             ← TOOL_NOT_FOUND
  → validate(kwargs, schema)         ← VALIDATION_ERROR
  → slot.handler(**kwargs)           ← await if awaitable
  → {"version": 1, "ok": true, "data": result}
Exception → ToolExecutionError → {"version": 1, "ok": false, "error": {...}}
```

## Registration Model

```python
# Internal to OpenCodeAdapter
@dataclass
class _ToolSlot:
    module: Module  # module instance for context
    handler: Callable  # resolved getattr(module, handler_name)
    schema: dict  # ToolDef.input_schema

# Registry: tool_name → _ToolSlot
_tool_registry: dict[str, _ToolSlot] = {}
```

Created during `register_module_tools()`, cleared on `stop()`. `start()` guards on `_registered_names` — if non-empty, skip registration (idempotent). Manager also checks: if `_registered_names` already has entries from a previous `start()` cycle, clear and re-register.

## Concurrency

- Registration: single-threaded, during `AgentAdapterManager.start()`. No concurrent access.
- Dispatch: FastMCP invokes handlers from the asyncio event loop. Registry is read-only after startup — no locking required.
- Future: if per-module servers are added (v1.1), each gets its own registry.

## File Changes

| File | Action |
|------|--------|
| `adapters/base.py` | ToolDef: add `handler_name: str`, make `input_schema` required non-empty |
| `adapters/opencode/server.py` | Replace `_make_tool_handler` stub with real dispatch; add `_ToolSlot`, `_validate_handler`, `_dispatch`; update `register_module_tools` |
| `adapters/manager.py` | **New**: `AgentAdapterManager` with discovery loop |
| `core/exceptions.py` | Add `ToolExecutionError` with `code` attribute |
| `core/engine.py` | No changes — intentionally adapter-unaware |
| `modules/vision/module.py` | Update `get_tool_defs()`: add `handler_name` to each ToolDef |
| `modules/chronicle/module.py` | Add `get_tool_defs()` with 2 tools |
| `modules/guardian/module.py` | Add `get_tool_defs()` with 2 tools |
| `cli/mcp.py` | Route `start`/`restart` through `AgentAdapterManager` instead of raw adapter |
| `tests/test_opencode_adapter.py` | Add dispatch, validation, error tests |
| `tests/test_tool_runtime.py` | **New**: unit tests + 1 E2E with real FastMCP |

## Interfaces / Contracts

- `ToolDef`: add `handler_name: str` (mandatory), `input_schema` no longer optional
- `ToolExecutionError(code, message, details)`: codes are `VALIDATION_ERROR`, `TOOL_NOT_FOUND`, `HANDLER_NOT_FOUND`, `MODULE_ERROR`, `INTERNAL_ERROR`
- `AgentAdapterManager(adapter, registry, config)`: `start()` → adapter.start + engine.start + discover + register; `stop()` → adapter.stop + engine.stop

## Testing Strategy

| Layer | Approach |
|-------|----------|
| Unit | Mock FastMCP, test `_validate_handler`, `_dispatch`, response formatting, error codes |
| Unit | Test `register_module_tools` with invalid handler_name → HANDLER_NOT_FOUND |
| Unit | Test sync vs async handler dispatch |
| Integration | Real FastMCP, mock module with get_tool_defs(), verify tools/list and tools/call |
| E2E | One test: create adapter → discover + register → call tool via FastMCP → verify structured response |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. `_make_tool_handler` stub is replaced inline. Tests for the old stub pattern are updated.

## Open Questions

- [ ] `handler_name` enforcement: reject callables passed directly or only string names allowed by ToolDef type?
- [ ] Schema validation: use `jsonschema.validate()` directly or wrap in adapter boundary?
