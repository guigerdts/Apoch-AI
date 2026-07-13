# Proposal: Apoch-AI Base Architecture — Module System, Plugins, OpenCode Integration, CLI

## Intent

Greenfield architecture for Apoch-AI: a modular, agent-agnostic framework providing AI-assisted development capabilities through a CLI tool and MCP server. The Core must never depend on any agent (OpenCode, Gentle-AI, etc.) — all agent communication goes through Adapters.

Architectural distinction: **Modules** are official Apoch-AI capabilities (Chronicle, Guardian, Vision, etc.). **Plugins** are the extension mechanism used by both official modules and third-party extensions. They may share internal lifecycle and API, but the architecture treats them as distinct concepts.

## Scope

### In Scope
- Core engine (direct lifecycle hooks + optional event bus)
- Module system (entry point discovery + config override)
- CLI: `apoch install`, `uninstall`, `list`, `status`, `mcp`, `config`, `doctor`
- Agent adapter ABC + OpenCode MCP gateway (single-process, stdio)
- Plugin manager (extension mechanism for official modules and third-party extensions; shares lifecycle ABC with modules)
- Stack integration (OpenSpec, Engram, Context7, CodeGraph detection)
- MVP modules: Chronicle, Guardian, Vision
- opencode.json management (backup, diff, consent, rollback)
- CLI command name: `apoch`

### Out of Scope
- Per-module MCP servers (deferred to v1.1+)
- TUI dashboard (optional future module)
- Plugin marketplace or remote registry
- Oracle, Pulse, Optimizer modules (v1.1+ candidates)
- Remote agent adapters (future)

## Capabilities

### New Capabilities
- `module-system`: Module discovery via entry points, lifecycle ABC, config override
- `cli-interface`: `apoch` subcommands (install, uninstall, list, status, mcp, config, doctor)
- `agent-adapter`: Adapter ABC + OpenCode MCP gateway (stdio); path to per-module split
- `module-chronicle`: Activity recording, timeline storage, query interface
- `module-guardian`: Scope protection, execution boundaries, exception isolation
- `module-vision`: Observability, structured logging, context inspection

### Modified Capabilities
None — greenfield project, no existing specs.

## Approach

| Area | Decision |
|------|----------|
| Core Engine | Direct lifecycle hooks (init/start/stop/shutdown) + optional event bus |
| Module System | `importlib.metadata.entry_points` discovery + YAML config override |
| Plugin System | Extension mechanism for official modules and third-party code; shares lifecycle ABC with modules but is a distinct architectural concept |
| OpenCode Integration | Single gateway MCP server (FastMCP stdio); paths to per-module split |
| Entry Point | CLI-first with typer, `apoch` command |
| Core Stack | Managed installer — detects Gentle-AI and defers when present; standalone otherwise |
| opencode.json | Backup before edit, show diff, ask consent, rollback via `apoch uninstall` |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `apoch/` | New | Top-level package (all code new) |
| `pyproject.toml` | New | Project metadata, scripts, entry points |
| `tests/` | New | Test suite per module (TDD required) |
| `openspec/specs/` | New | Capability specs (6 new spec directories) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| MCP protocol version changes | Medium | Pin OpenCode compatibility range in metadata |
| Single gateway crash domain | Medium | Per-module exception boundaries and try/except guards |
| Gentle-AI duplicate management | Medium | Detect prior install; defer to it (Rule 010) |
| Cross-platform stdio MCP (Windows) | Low | Portable SIGTERM handling, explicit process cleanup |

## Rollback Plan

1. `apoch uninstall` restores opencode.json from backup, removes MCP server config
2. `uv tool uninstall apoch` removes the package
3. Entry point modules deactivate automatically when package is removed
4. All stack changes are reversible per Project Rule 007

## Dependencies

- Python 3.13+
- uv (build, packaging, dependency management)
- OpenCode with MCP support (v1 protocol)
- Optional: typer/click, pydantic (MCP schema), pyyaml (config)

## Success Criteria

- [ ] `apoch install` configures OpenCode integration and verifies MCP server connectivity
- [ ] `apoch list` shows discovered modules with enable/disable status
- [ ] `apoch status` reports healthy gateway process with module health
- [ ] MVP Module (Chronicle) loads, initializes, and exposes at least one tool via MCP
- [ ] `apoch uninstall` fully reverts opencode.json to exact pre-install state
- [ ] TDD: all spec scenarios pass with coverage ≥ 80%
- [ ] Module crash does not bring down entire gateway (exception boundary proven)
