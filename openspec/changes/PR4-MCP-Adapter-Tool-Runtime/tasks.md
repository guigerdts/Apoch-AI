# Tasks: PR4 — MCP Adapter / Tool Runtime

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Work Units

| Unit | Goal | PR | Focused test | Harness | Rollback |
|------|------|----|-------------|---------|----------|
| 1 | Runtime Foundation — ToolDef+handler, _ToolSlot, AgentAdapterManager, handler validation | PR4A | `pytest tests/test_opencode_adapter.py -x` | `apoch mcp start` followed by `pytest` | Revert adapters/base.py + manager.py + exceptions.py |
| 2 | Dispatch Runtime — schema validation, dispatch, response, Chronicle+Guardian get_tool_defs | PR4B | `pytest tests/test_tool_runtime.py -x` | Full FastMCP E2E test | Revert adapters/opencode/server.py dispatch |

## PR4A — Runtime Foundation

- [x] 1.1 ToolDef: add `handler_name: str` (mandatory, breaking) and make `input_schema` required in `adapters/base.py`
- [x] 1.2 `ToolExecutionError` with `code` attribute in `core/exceptions.py`; add 5 error constants
- [x] 1.3 `_ToolSlot` dataclass + `_tool_registry` dict + handler validation (existence, public, no `_`) in `register_module_tools()`
- [x] 1.4 `AgentAdapterManager` in `adapters/manager.py`: `start()` (adapter.start → engine.start → discover → register) + `stop()` (adapter.stop + engine.stop)
- [x] 1.5 Route `cli/mcp.py` `start`/`restart` through `AgentAdapterManager` instead of raw adapter
- [x] 1.6 Unit tests: handler validation (valid name, non-existent, private), `_ToolSlot` creation, `AgentAdapterManager` discovery loop idempotence
- [x] 1.7 Acceptance: `pytest` 100% green, `ruff check` clean, `uv build` ok

## PR4B — Dispatch Runtime

- [ ] 2.1 `_dispatch()` in `_make_tool_handler`: lookup `_tool_registry` → `TOOL_NOT_FOUND`, validate kwargs with `jsonschema.validate()` → `VALIDATION_ERROR`, call handler, `isawaitable()` check → await if needed
- [ ] 2.2 Wrap dispatch in try/except: `ToolExecutionError` → structured error, any other exception → `MODULE_ERROR` / `INTERNAL_ERROR`
- [ ] 2.3 Structured response formatting: success `{"version": 1, "ok": true, "data": result}`, error `{"version": 1, "ok": false, "error": {"code": "...", "message": "..."}}`
- [ ] 2.4 VisionModule: update `get_tool_defs()` — add `handler_name` to all 4 ToolDef entries
- [ ] 2.5 ChronicleModule: add `get_tool_defs()` with chronicle_query (handler_name="query") and chronicle_stats (handler_name="stats")
- [ ] 2.6 GuardianModule: add `get_tool_defs()` with guardian_diagnostics (handler_name="diagnostics") and guardian_alldiagnostics (handler_name="all_diagnostics")
- [ ] 2.7 Tests: unit tests for schema validation, successful dispatch (sync + async), unknown tool, handler exception mapping
- [ ] 2.8 E2E test: real FastMCP with mock module → `tools/list` verifies registration → `tools/call` verifies structured response
- [ ] 2.9 Acceptance: `pytest` 100% green (including 309 existing tests), `ruff check` clean, `uv build` ok, CHANGELOG updated, OpenSpec synced
