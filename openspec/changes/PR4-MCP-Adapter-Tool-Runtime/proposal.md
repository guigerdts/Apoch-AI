# Proposal: PR4 — MCP Adapter / Tool Runtime

## Intent

Today `_make_tool_handler()` creates stubs that echo kwargs — tools never call a module method. PR4 wires the dispatch layer: validate JSON Schema, route to the handler, return structured responses with error handling.

## Scope

### In Scope
- ToolDef: add `handler_name: str` (breaking, mandatory). Must be a public method name, must exist at registration time, no `_`-prefixed or arbitrary callable
- Dispatch: schema validation → handler resolution → method call → structured response
- `ToolExecutionError` with codes: `VALIDATION_ERROR`, `TOOL_NOT_FOUND`, `HANDLER_NOT_FOUND`, `MODULE_ERROR`, `INTERNAL_ERROR`
- Response contract: `{"version": 1, "ok": true, "data": ...}` / `{"version": 1, "ok": false, "error": {"code": "...", "message": "..."}}`. `details` optional on errors.
- Sync/async: `inspect.isawaitable()` — transparent
- Discovery loop in `Engine.start()` — auto-register all modules with `get_tool_defs()`, idempotent, deterministic (alphabetical module order)
- `get_tool_defs()` for Chronicle (2 tools) and Guardian (2 tools)
- VisionModule: update existing `get_tool_defs()` with `handler_name`

### Out of Scope
Streaming, permissions, auth, cancellation, rate limiting, per-module servers, remote adapters, SSE.

## Capabilities

### New
- `tool-runtime`: dispatch, schema validation, handler resolution, structured responses

### Modified
- `agent-adapter`: `register_module_tools()` wires real dispatch, validates, returns structured responses
- `module-vision`: update ToolDefs with `handler_name` + structured responses
- `module-chronicle`: add `get_tool_defs()` (chronicle_query, chronicle_stats)
- `module-guardian`: add `get_tool_defs()` (guardian_diagnostics, guardian_alldiagnostics)

## Approach

```
Tool call → FastMCP → Adapter:
  1. Validate kwargs vs ToolDef.input_schema
  2. Resolve handler: getattr(module, handler_name)
  3. Call handler(**kwargs), await if awaitable
  4. Wrap: {"version": 1, "ok": true, "data": result}
  5. Exception → ToolExecutionError → {"ok": false, "error": {...}}
```

Engine.start() auto-registers all `get_tool_defs()` modules.

## Affected Areas

`adapters/base.py`, `adapters/opencode/server.py`, `core/engine.py`, `core/exceptions.py`, `modules/vision/module.py`, `modules/chronicle/module.py`, `modules/guardian/module.py`, `tests/test_opencode_adapter.py`, `tests/test_tool_runtime.py` (new).

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Discovery breaks Engine.start() idempotence | Low | Guard on `_registered_names` |
| `jsonschema` dependency weight | Low | Already transitive via FastMCP |

## Rollback Plan

Revert `register_module_tools()` to `_make_tool_handler` stub. Remove discovery loop. Stubs echo kwargs — no breakage.

## Dependencies

`jsonschema` (declare explicitly if not already transitive).

## Success Criteria

- [ ] `handler_name` validated at registration: must be public method name, exists, no `_`-prefix
- [ ] ToolDef with valid `handler_name` dispatches to correct module method
- [ ] Invalid kwargs → `VALIDATION_ERROR` — handler never invoked
- [ ] Unknown tool → `TOOL_NOT_FOUND`
- [ ] Missing handler → `HANDLER_NOT_FOUND`
- [ ] Module exception → `MODULE_ERROR` with traceback in `details`
- [ ] Chronicle + Guardian expose 2 dispatchable tools each
- [ ] Engine.start() registers all tools deterministically; second start() no dups
- [ ] Sync and async handlers both work
- [ ] `{"version": 1, ...}` contract enforced in all success and error paths
