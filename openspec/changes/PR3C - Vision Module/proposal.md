# Proposal: PR3C — Vision Module

## Intent

Create Apoch-AI's third concrete module — the Vision — providing structured logging, MCP-exposed observability tools, and optional integration with Chronicle for long-term event archival. Vision gives AI agents and developers visibility into Apoch-AI's internals: module states, configuration, live log window, and system health.

## Scope

### In Scope

1. **Structured logging** (`vision.log()`) — NDJSON rotating log files with configurable size/backup count, severity levels (DEBUG, INFO, WARN, ERROR, FATAL), and structured context payloads.
2. **MCP tool: `vision.state`** — returns current state (RUNNING/STOPPED/FAILED) for all loaded modules plus gateway health.
3. **MCP tool: `vision.config`** — returns effective config for a single module or all modules.
4. **MCP tool: `vision.logs`** — query recent log entries with optional filters (level, module, limit).
5. **MCP tool: `vision.system`** — process health: PID, Python version, platform, uptime, memory RSS.
6. **Log entry memory buffer** — last N entries queryable via `vision.recent()`.
7. **Optional integration with Chronicle** — push structured events to Chronicle for permanent storage when Chronicle is loaded.
8. **Graceful degradation** — unwritable log dir, JSON serialization failure, missing Chronicle → Vision degrades without crashing.

### Out of Scope (deferred to future releases)

- Grafana/Datadog integration
- Distributed tracing
- APM-style performance metrics
- Real-time log streaming
- Log viewer TUI module
- Sensitive config redaction policy

## Design Constraints (NON-NEGOTIABLE)

1. **Chronicle integration via DI only** — Vision MUST NOT import `apoch.modules.chronicle`. Chronicle MUST NOT import Vision. The Core must NOT gain specific knowledge of either module. Integration uses duck-typed callable injection through `Context.services`.
2. **No circular dependencies** — Vision imports from `apoch.core.*` and stdlib only. No cross-module imports.
3. **No event bus / messaging framework** — the existing EventBus is not extended, no new message infrastructure is introduced.
4. **Bootstrap must remain minimal** — Engine changes must be zero or one generic extension point. No Engine changes that reference specific module names.
5. **Integration must be optional** — if Chronicle is not loaded, Vision operates normally, degrading only the event-archival feature.
6. **No psutil** — system info uses stdlib (`platform`, `os`, `/proc/self/status`).
7. **Clean Architecture intact** — Core imports zero module code, Engine unchanged from module-specific knowledge.

## Architecture Approach

### Layers

```
VisionModule(Module)
├── log() → NDJSON → RotatingFileHandler
├── recent() → in-memory ring buffer
├── module_state() → via Context.registry
├── module_config() → via Context.registry
├── system_info() → os / platform / /proc
└── start() reads context.services["chronicle.record"]
```

### Chronicle Integration — Injection Strategy

- **Context** gains a `services: dict[str, Callable]` field (generic, no module names).
- **ChronicleModule** exposes a `@property services` returning `{"chronicle.record": self.record}`.
- **ModuleRegistry.start_all()** gathers services from all loaded modules via generic `hasattr` check before calling any module's `start()`. (Same duck-typing pattern as existing Guardian integration.)
- **VisionModule.start()** reads `context.services.get("chronicle.record")` and stores it. If `None`, event archival is skipped.
- **No Engine changes** for the wiring — it's entirely within Registry's existing start_all flow.

### Module State / Config Access

- **Context** gains a `registry` field (`ModuleRegistry | None`), set by Engine before start_all.
- Vision reads `context.registry.loaded` to iterate modules and their `state` / config values.
- No module-specific names in Core — Engine just sets `context.registry = self._registry`.

### MCP Tools

- Vision registers tools via `register_module_tools()` on the adapter during `start()`.
- Tools: `vision_state`, `vision_config`, `vision_logs`, `vision_system`.
- The adapter handles name prefixing for duplicates.

### Files to Create

| File | Purpose |
|------|---------|
| `src/apoch/modules/vision/__init__.py` | Lazy-export VisionModule |
| `src/apoch/modules/vision/module.py` | VisionModule class |
| `src/apoch/modules/vision/models.py` | LogRecord, SystemInfo dataclasses |

### Config

```yaml
vision:
  enabled: true
  log_dir: "~/.local/share/apoch/logs/"
  log_file: "vision.ndjson"
  max_bytes: 1_048_576   # 1 MB
  backup_count: 3
  buffer_size: 1000       # in-memory recent entries
```

## Core/Context Changes Required

1. **`core/module.py` — Context**: add two generic fields:
   - `services: dict[str, Callable] = field(default_factory=dict)`
   - `registry: ModuleRegistry | None = None`
2. **`core/registry.py` — start_all**: add generic service gathering loop before lifecycle calls (uses `hasattr`, no module names).
3. **`core/engine.py` — start**: set `context.registry = self._registry` (one line, generic).

All changes are module-agnostic — no module names appear in Core code.

## Estimated Effort

| Component | Est. Lines |
|-----------|-----------|
| Models (LogRecord, SystemInfo) | ~40 |
| VisionModule | ~220 |
| Module init + entry point | ~10 |
| Tests | ~200 |
| **Total** | **~470** |

## Risks

| Risk | Mitigation |
|------|------------|
| Service gathering in Registry adds complexity to Core | `< 10 LOC`, same duck-typing pattern as existing Guardian wiring |
| MCP tools are untested end-to-end (no MCP infra in tests) | Test Vision's log/state/system query methods directly, not via MCP transport |
| `/proc/self/status` is Linux-only | Fallback: return `memory_rss_mb: None` on other platforms; Vision still functional |

## Next Phase

Design — concrete class diagram, method signatures, and wiring plan.
