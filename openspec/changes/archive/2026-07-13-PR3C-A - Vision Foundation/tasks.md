# Tasks: PR3C — Vision Module

## PR Split

| PR | Scope | Tasks | Est. LOC |
|----|-------|-------|----------|
| **PR3C-A** | Foundation + Vision Core + Logging + Services + Service gathering tests + Degraded foundation tests | 1.1–1.4, 2.1–2.3, 3.1–3.2, 5.1, 5.2 | ~280 |
| **PR3C-B** | Query APIs + get_tool_defs + Integration E2E + Degraded query tests | 4.1–4.5, 5.2b, 5.3 | ~200 |

**Stacked to main**: PR3C-A → main, PR3C-B → main (independientes, mergeables).

---

## Phase 1 — Foundation (Core changes + Models)

### 1.1 Add `services` and `registry` fields to Context  [PR3C-A]

**File**: `src/apoch/core/module.py`
**Est**: ~10 LOC

- Add `services: dict[str, Callable] = field(default_factory=dict)` to Context dataclass
- Add `registry: ModuleRegistry | None = None` to Context dataclass
- Use `TYPE_CHECKING` import for `ModuleRegistry` to avoid circular import (module.py → registry.py → module.py)
- Both fields are completely generic — zero module names

**RED**: Test that Context() creates with empty services and None registry
**GREEN**: Add fields
**REFACTOR**: — (trivial)

### 1.2 Add service gathering + collision detection to Registry.start_all()  [PR3C-A]

**File**: `src/apoch/core/registry.py`
**Est**: ~15 LOC

- Before the lifecycle loop, iterate `self._loaded.values()`
- For each module, `getattr(mod, "services", None)`
- If it's a dict, check each key for collision with existing context.services
- On collision → `logger.critical()` + raise `ModuleLoadError`
- If no collision, `context.services.update(svc)`
- Services dict is immutable after this point (no module adds at runtime)

**RED**: Test that Registry.start_all() gathers services from a mock module
**RED**: Test that key collision raises ModuleLoadError
**RED**: Test that module without services is silently skipped

**GREEN**: Implement gathering loop + collision detection

**REFACTOR**: Extract collision check to private helper if logic grows

### 1.3 Wire `context.registry` in Engine.start()  [PR3C-A]

**File**: `src/apoch/core/engine.py`
**Est**: 1 LOC

- After `self._context = Context()`, add `self._context.registry = self._registry`
- This is the only Engine change in PR3C

**RED**: Test that Engine creates Context with registry set
**GREEN**: Add one assignment line
**REFACTOR**: — (trivial)

### 1.4 Create Vision data models  [PR3C-A]

**File**: `src/apoch/modules/vision/models.py`
**Est**: ~40 LOC

- `LogRecord` dataclass: timestamp, level, message, module (str|None), context (dict), pid (int)
- `SystemInfo` dataclass: python_version, platform, pid, uptime_seconds, memory_rss_mb (float|None)
- `__all__` export

**RED**: Test creating LogRecord with all fields
**RED**: Test SystemInfo with None memory_rss_mb
**GREEN**: Define dataclasses
**REFACTOR**: — (trivial)

## Phase 2 — Vision Core (Logging + Lifecycle)

### 2.1 VisionModule scaffold with lifecycle  [PR3C-A]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~50 LOC

- `VisionModule(Module)` with `__init__`, `start()`, `stop()`, `shutdown()`
- Config keys: log_dir, log_file, max_bytes, backup_count, buffer_size
- In-memory ring buffer: `deque[LogRecord](maxlen=buffer_size)`
- `start()` captures `event_sink = context.services.get("chronicle.record")`
- `start()` captures `self._registry = context.registry`
- `start()` records `self._started_at = time.monotonic()`

**RED**: Test lifecycle transitions LOADED → RUNNING → STOPPED → SHUTDOWN
**RED**: Test start() captures services and registry from context
**RED**: Test start() works with empty context (no services, no registry)
**GREEN**: Implement lifecycle methods + context capture
**REFACTOR**: — (trivial given existing Module ABC)

### 2.2 Implement `log()` method — JSON formatting + file output  [PR3C-A]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~60 LOC

- `log(level, message, *, module=None, **kw)` creates `LogRecord`
- Appends to ring buffer
- Serializes to NDJSON via `RotatingFileHandler` with custom JSON formatter
- FATAL level triggers immediate `flush()`
- JSON serialization failure for a context key → skip that key, log warning, preserve others
- Log directory unwritable at init → log warning, no handler, Vision degraded
- Log directory unwritable at rotation → log warning, continue degraded

**RED**: Test log() writes entry to buffer (visible via recent())
**RED**: Test log() writes NDJSON line to file
**RED**: Test log() with structured context → JSON in file
**RED**: Test FATAL level flushes immediately
**RED**: Test json serialization failure skips problematic key
**RED**: Test unwritable log dir → no crash, Vision degraded

**GREEN**: Implement log() with JSON formatter + RotatingFileHandler
**REFACTOR**: Extract `_format_json()` and `_write_to_file()` helpers

### 2.3 Create Vision `__init__.py` + entry point  [PR3C-A]

**Files**: `src/apoch/modules/vision/__init__.py`, `pyproject.toml`
**Est**: ~15 LOC

- Lazy-export `VisionModule` via `__getattr__` (same pattern as Chronicle/Guardian)
- Add `vision = "apoch.modules.vision.module:VisionModule"` under `[project.entry-points."apoch.modules"]`

**RED**: Test that `from apoch.modules.vision import VisionModule` resolves
**RED**: Test that entry point resolves (uv run python -c ...)
**GREEN**: Create __init__.py, add pyproject.toml entry
**REFACTOR**: — (trivial, established pattern)

## Phase 3 — Services (Chronicle Integration)

### 3.1 Add `services` property to ChronicleModule  [PR3C-A]

**File**: `src/apoch/modules/chronicle/module.py`
**Est**: ~5 LOC

- `@property def services(self) -> dict[str, Callable]:` returning `{"chronicle.record": self.record}`
- This is the ONLY change to Chronicle in PR3C

**RED**: Test that ChronicleModule().services returns dict with "chronicle.record" key
**RED**: Test that calling the service invokes ChronicleModule.record()
**GREEN**: Add @property
**REFACTOR**: — (trivial, one property)

### 3.2 Wire optional Chronicle archival in Vision.log()  [PR3C-A]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~15 LOC

- In `log()`, if `self._event_sink is not None`:
  - Convert `LogRecord` → `ActivityEvent` (or use simple dict)
  - Fire-and-forget: `asyncio.ensure_future(self._event_sink(event))`
  - If callable raises, log warning and continue
- Test that event_sink is called when Chronicle is loaded
- Test that log() works normally when event_sink is None

**RED**: Test log() calls event_sink when set
**RED**: Test log() works without event_sink
**RED**: Test event_sink failure doesn't crash Vision

**GREEN**: Implement event_sink dispatch in log()
**REFACTOR**: — (trivial, the error handling is already planned)

## Phase 4 — Query APIs (MCP Tool Handlers)

### 4.1 Implement `recent()`  [PR3C-B]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~20 LOC

- `async def recent(self, limit=50, level=None) -> list[LogRecord]`
- Returns from ring buffer, newest first
- Filter by level if specified
- Cap at limit

**RED**: Test returns buffered entries
**RED**: Test level filter works
**RED**: Test limit works
**RED**: Test empty buffer returns []

**GREEN**: Implement recent()
**REFACTOR**: — (simple slice + filter)

### 4.2 Implement `module_state()`  [PR3C-B]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~30 LOC

- `async def module_state(self, name=None) -> dict`
- If no registry → return `{}`
- If name is None → return all modules: `{name: state.value}`
- If name is set and not found → return `{name: {"not_found": True}}`
- Uses `registry.loaded` (read-only view from Registry)

**RED**: Test returns all module states from mock registry
**RED**: Test single module state
**RED**: Test unknown module returns not_found
**RED**: Test no registry → empty dict

**GREEN**: Implement module_state()
**REFACTOR**: — (straightforward dict comprehension)

### 4.3 Implement `module_config()`  [PR3C-B]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~25 LOC

- `async def module_config(self, name=None) -> dict`
- If no registry → return `{}`
- If name is set → return config for that module (from its `_config` attr)
- If name is not found → return `{name: {"not_found": True}}`

**RED**: Test returns config for a module
**RED**: Test unknown module
**RED**: Test no registry → empty dict

**GREEN**: Implement module_config()
**REFACTOR**: — (straightforward)

### 4.4 Implement `system_info()`  [PR3C-B]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~35 LOC

- `async def system_info(self) -> SystemInfo`
- PID: `os.getpid()`
- Python version: `platform.python_version()`
- Platform: `platform.platform()`
- Uptime: `time.monotonic() - self._started_at`
- Memory RSS: read `/proc/self/status` (Linux) → parse `VmRSS:` line
- Non-Linux → `memory_rss_mb: None`

**RED**: Test PID matches os.getpid()
**RED**: Test python_version is not empty
**RED**: Test platform is not empty
**RED**: Test uptime_seconds > 0
**RED**: Test memory_rss_mb > 0 on Linux
**RED**: Test memory_rss_mb is None on non-Linux (mock platform)

**GREEN**: Implement system_info()
**REFACTOR**: Extract `_read_memory_rss()` helper

### 4.5 Implement `get_tool_defs()`  [PR3C-B]

**File**: `src/apoch/modules/vision/module.py`
**Est**: ~20 LOC

- `def get_tool_defs(self) -> list[ToolDef]`
- Returns 4 ToolDef entries: vision_state, vision_config, vision_logs, vision_system
- Each with name, description, and input_schema dict
- Registration with adapter is deferred (external wiring, not Vision's responsibility)

**RED**: Test returns 4 ToolDef entries
**RED**: Test each has name, description, input_schema

**GREEN**: Implement get_tool_defs()
**REFACTOR**: — (trivial data)

## Phase 5 — Integration + Edge Cases

### 5.1 Test service gathering end-to-end  [PR3C-A]

**File**: `tests/test_registry.py` (existing)
**Est**: ~40 LOC

- Create mock module with `services` property
- Create mock module without `services` property
- Verify Registry.start_all() populates context.services correctly
- Verify collision detection raises ModuleLoadError
- Verify module without services is skipped silently

**RED**: Write tests (existing test_registry.py has test infrastructure)
**GREEN**: Already implemented in 1.2 — verify they pass
**REFACTOR**: — (already covered)

### 5.2 Test degraded modes — Foundation  [PR3C-A]

**File**: `tests/modules/vision/test_vision.py`
**Est**: ~20 LOC

- Vision with empty context → start() works, event_sink is None
- Vision with no log dir → operates without file handler
- Vision with no event_sink → normal operation, no Chronicle push
- event_sink that raises → vision continues, entry not archived

**RED**: Write degraded-mode tests for Foundation scope
**GREEN**: VisionModule handles all degraded cases (2.2, 3.2)
**REFACTOR**: — (already handled in implementation tasks)

### 5.2b Test degraded modes — Query APIs  [PR3C-B]

**File**: `tests/modules/vision/test_vision.py`
**Est**: ~15 LOC

- Vision with no registry → module_state() returns {}, module_config() returns {}
- Vision with unknown module → not_found dict returned
- Vision with no buffer → recent() returns []

**RED**: Write degraded-mode tests for Query API scope
**GREEN**: VisionModule handles all degraded cases (4.2-4.4)
**REFACTOR**: — (already handled in implementation tasks)

### 5.3 Verify full integration with Chronicle  [PR3C-B]

**File**: `tests/modules/vision/test_vision.py`
**Est**: ~30 LOC

- Create mock Chronicle that exposes `services = {"chronicle.record": record}`
- Create Registry with both Chronicle and Vision loaded
- Run start_all → verify services are gathered
- Call Vision.log() → verify Chronicle.record() was called
- Verify Vision degrades when Chronicle not loaded

**RED**: Write integration test
**GREEN**: Verify with real module instances
**REFACTOR**: — (end-to-end verification)

## Task Dependency Graph

```
PR3C-A (Foundation):
1.1 ──→ 1.2 ──→ 1.3 ──→ 2.1 ──→ 2.2 ──→ 3.2 ──→ 5.2
                           │        │
1.4 ───────────────────────┘        3.1 ────┘
                     2.3 ── (anytime after 2.1)
                     5.1 ── (after 1.2)

PR3C-B (Query APIs):
4.1 ──→ 4.4 ──→ 5.2b
  │              │
  4.2 ──→ 4.5    │
  │              │
  4.3 ───────────┘
  5.3 ── (after PR3C-A merged)
```

## Review Workload Forecast

| Field | PR3C-A | PR3C-B |
|-------|--------|--------|
| Estimated changed lines | ~280 | ~200 |
| 400-line budget risk | Low | Low |
| Chain strategy | Stacked to main | Stacked to main |
| Mergeable independently | ✅ Yes | ✅ Yes |

## Strict TDD Mode

- RED test first for every task
- GREEN minimal implementation
- TRIANGULATE + REFACTOR after each task
- Run full suite before each commit
