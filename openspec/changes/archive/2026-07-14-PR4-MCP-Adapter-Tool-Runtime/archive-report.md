# Archive Report — PR4: MCP Adapter / Tool Runtime

## Change
- **Name**: PR4 — MCP Adapter / Tool Runtime
- **Archive date**: 2026-07-14
- **Version**: v0.7.0-alpha
- **Strategy**: Stacked to main (PR4A → PR4B → main)

## Tasks Completed (15/15)

### PR4A — Runtime Foundation

| # | Task | Status |
|---|------|--------|
| 1.1 | ToolDef: add `handler_name: str` (mandatory, breaking) and make `input_schema` required | ✅ `adapters/base.py` |
| 1.2 | `ToolExecutionError` with `code` attribute + 5 error constants | ✅ `core/exceptions.py` |
| 1.3 | `_ToolSlot` dataclass + `_tool_registry` + handler validation | ✅ `adapters/opencode/server.py` |
| 1.4 | `AgentAdapterManager` — discovery loop orchestrator | ✅ `adapters/manager.py` |
| 1.5 | Route `cli/mcp.py` through `AgentAdapterManager` | ✅ `cli/mcp.py` |
| 1.6 | Unit tests: handler validation, _ToolSlot, manager idempotence | ✅ `tests/test_opencode_adapter.py` |
| 1.7 | Acceptance: pytest green, ruff clean, uv build ok | ✅ |

### PR4B — Dispatch Runtime

| # | Task | Status |
|---|------|--------|
| 2.1 | `_dispatch()` — tool lookup, `jsonschema.validate()`, sync/async dispatch | ✅ `adapters/opencode/server.py` |
| 2.2 | try/except: ToolExecutionError → structured error, Exception → INTERNAL_ERROR | ✅ |
| 2.3 | Structured response: `{"version": 1, "ok": bool, "data"/"error": ...}` | ✅ |
| 2.4 | VisionModule: update `get_tool_defs()` with `handler_name` | ✅ `modules/vision/module.py` |
| 2.5 | ChronicleModule: add `get_tool_defs()` (3 tools) | ✅ `modules/chronicle/module.py` |
| 2.6 | GuardianModule: add `get_tool_defs()` (4 tools) | ✅ `modules/guardian/module.py` |
| 2.7 | Unit tests: schema validation, sync/async dispatch, error mapping | ✅ |
| 2.8 | E2E test: real FastMCP + stdio client → tools/list + tools/call | ✅ `tests/test_e2e_mcp.py` |
| 2.9 | Acceptance: 342 tests, ruff clean, uv build ok, CHANGELOG updated | ✅ |

## Files Changed

| File | Action |
|------|--------|
| `adapters/base.py` | `ToolDef.handler_name` + `input_schema` required |
| `adapters/opencode/server.py` | Replace stub with real `_dispatch`, `_ToolSlot`, `_validate_handler`, `_override_tool_arg_model` |
| `adapters/manager.py` | **New**: `AgentAdapterManager` |
| `core/exceptions.py` | Add `ToolExecutionError` |
| `core/engine.py` | No changes (intentionally adapter-unaware) |
| `modules/chronicle/module.py` | Add `get_tool_defs()` |
| `modules/guardian/module.py` | Add `get_tool_defs()` |
| `modules/vision/module.py` | Update `get_tool_defs()` with `handler_name` |
| `cli/mcp.py` | Route through `AgentAdapterManager` |
| `tests/test_opencode_adapter.py` | Dispatch + validation + error tests |
| `tests/test_e2e_mcp.py` | **New**: 11 E2E tests with real MCP protocol |
| `tests/_mcp_e2e_server.py` | **New**: E2E server subprocess entry point |
| `pyproject.toml` | Add `jsonschema` dep, pytest-asyncio `loop_scope=module` |
| `CHANGELOG.md` | Document v0.7.0-alpha |

## Verification Summary

- Tests: **342/342 pass** (331 unit + 11 E2E)
- Lint: 0 new issues (15 pre-existing E501 accepted)
- Build: `uv build` — sdist + wheel OK
- Architecture: Dispatch is a plain method on `OpenCodeAdapter` — zero FastMCP leak. `_ToolSlot` stores only `handler` + `schema`. `AgentAdapterManager` imports no adapters. `get_tool_defs()` uses lazy `ToolDef` imports.
- E2E gate: validates full stack (engine + adapter + 3 modules + 11 tools) against real MCP stdio protocol

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Discovery loop in `AgentAdapterManager`, not Engine | Core must not import `adapters/*` |
| `_ToolSlot` stores handler + schema only | No module reference stored |
| Registration-time handler validation | Catches config errors at startup |
| Sync/async via `inspect.isawaitable()` | Zero boilerplate for module authors |
| `_override_tool_arg_model()` replaces FastMCP auto-generated model | `**kwargs` handler generates wrong Pydantic model |

## SDD Artifacts

Proposal, specs (4), design, and tasks are archived alongside this report.

## Status

PR4 completes the approved Phase 2 (OpenCode Integration) extension for tool dispatch.
Development continues per the frozen Master Document roadmap: Phase 3 (Core Modules)
with Pulse, Optimizer, Oracle pending; Phase 4 (Ecosystem); Phase 5 (Stabilization).
