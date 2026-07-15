# Roadmap

## ✅ Completed

- **Core Stack Implementation** (PR5.1–PR5.3) — StackComponent, StackManager, StackState FSM, CommandRunner, StackRegistry, entry-point discovery, CLI `apoch stack` commands
- **OpenSpec Adapter** (PR5) — Reference component, 41 tests
- **Engram Adapter** (PR6) — Platform-dispatch install, 48 tests
- **Context7 Adapter** (PR7) — No-doctor pattern, 36 tests
- **CodeGraph Adapter** (PR8) — JSON health strategy, 31 tests
- **CLI Stack Commands** — `apoch stack status`, `install`, `uninstall`, `verify`
- **Chronicle Module** — Activity recording with SQLite, 35+ tests
- **Guardian Module** — Exception isolation and execution boundaries, 25 tests
- **Vision Module** — Observability suite, NDJSON logging, introspection
- **OpenCode Adapter** — FastMCP gateway, tool dispatch, opencode.json management
- **1,105 Tests** — Clean Ruff, `v0.7.0-alpha` tagged
- **Test Suite** — Full coverage of all lifecycle methods, edge cases, and integration paths

## 🔄 In Development

| Module | Status | Description |
|--------|--------|-------------|
| Oracle | Beta | Decision analysis and recommendation engine — implemented, not yet stable |
| Pulse | Beta | Performance benchmarking and metrics — v1 implemented |
| Optimizer | Beta | Context and token optimization — implemented |

## 📋 Planned

| Item | Scope | Notes |
|------|-------|-------|
| Documentation Completion | Docs | Fill remaining gaps in developer and user docs |
| Extended Agent Support | Agent Layer | Claude Code, Codex, Gemini CLI |
| Persistent Configuration | CLI | Config file for user preferences |
| CI/CD Pipeline | Infrastructure | GitHub Actions for tests, lint, build, release |

The roadmap is governed by the Project Master (`PROJECT_MASTER.md`). Any modification requires explicit approval through the SDD process. See [development.md](development.md) for setup instructions.
