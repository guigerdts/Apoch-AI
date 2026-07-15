# Design: Core Stack Installation & Lifecycle

## Technical Approach

Three-layer architecture: **CLI** (`apoch/cli/stack.py`) → **Stack** (`apoch/stack/`) → **Integrations** (uv/pip/git). StackManager orchestrates via StackComponent ABC — zero per-component logic. Component discovery via entry points (`apoch.stack.components`). Stack is independent from Core — `apoch/core/` never imports `apoch/stack/` (Rule 005).

## Architecture Principles (Cross-Cutting)

These principles govern ALL Stack code — no exceptions.

1. **Dependency Injection**: No component instantiates another directly. All resolution via StackRegistry, constructor injection, or interfaces. Zero hidden dependencies.
2. **StackPaths**: All filesystem access passes through a single `StackPaths` service. No hardcoded paths anywhere — guarantees cross-platform compatibility. File at `src/apoch/stack/paths.py`.
3. **Serialization Layer**: All StackManifest read/write through a single serialization module (`src/apoch/stack/manifest.py`). No `json.load`/`json.dump` scattered across the project.
4. **ClockProvider**: All timestamps obtained through a `ClockProvider` interface, never `datetime.now()` directly. Enables deterministic testing. File at `src/apoch/stack/clock.py`.
5. **CommandRunner**: Components never execute subprocesses directly. A common `CommandRunner` interface wraps all subprocess/spawn calls. Mockable in tests. File at `src/apoch/stack/runner.py`.
6. **Downloader**: No download logic embedded in components. A `Downloader` abstraction handles HTTP/Git/PyPI sources. File at `src/apoch/stack/downloader.py`.
7. **Observability via Events**: Components never use `logging` directly. All observability flows through the EventBus — log handlers attach to events externally.
8. **Testability**: Every component must be fully testable without Internet access. All external dependencies (subprocess, network, filesystem, clock) MUST be replaceable with mocks or fakes.

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| Stack vs Module | Module vs independent subsystem | Independent | Rule 005 — Core never depends |
| Discovery | Hardcoded vs entry-point registry | Entry-point registry | Matches existing `apoch.adapters` pattern, extensible |
| Rollback | Per-component vs monolithic | Per-component + transactional | Each component knows how to undo itself |
| Locking | In-memory vs file-based | File-based | Survives crashes, cross-process safe |
| Persistence | JSON vs YAML vs DB | JSON | Simple, atomic writes via temp→rename, terminal-friendly |
| State detection | Cached vs real | Real per-execution | Detects manual changes, no stale state |

## Package Structure

```
src/apoch/stack/
├── __init__.py       # Exports StackManager, StackRegistry, StackState
├── manager.py        # StackManager — orchestrator (injects deps)
├── registry.py       # StackRegistry — entry-point discovery
├── component.py      # StackComponent ABC
├── descriptor.py     # StackDescriptor dataclass
├── manifest.py       # StackManifest — serialization/deserialization (single layer)
├── state.py          # StackState enum (11 states + derive_state())
├── events.py         # Event type constants (stack.*)
├── lock.py           # FileLock — file-based operation lock
├── result.py         # OperationResult dataclass
├── paths.py          # StackPaths — all filesystem resolution (no hardcoded paths)
├── clock.py          # ClockProvider — injectable clock (no datetime.now)
├── runner.py         # CommandRunner — subprocess abstraction
├── downloader.py     # Downloader — HTTP/Git/PyPI download abstraction
└── exceptions.py     # StackError subclasses
```

## Data Flow

```
CLI Layer (apoch/cli/stack.py)
       │
       ▼
StackManager (apoch/stack/manager.py)  ← injected: StackRegistry, FileLock, ClockProvider, EventBus
        │
        ├──── StackRegistry ──── importlib.metadata ──── pyproject.toml entry points
        │
        ├──── StackComponent (ABC per component) ← injected: CommandRunner, Downloader
        │         detect() → install() → detect() → derive_state() → verify()
        │         health() runs functional checks beyond existence
        │
        ├──── FileLock (~/.config/apoch/stack.lock) ← resolved via StackPaths
        ├──── StackManifest (~/.config/apoch/stack-manifest.json) ← single serialization layer
        └──── EventBus (per operation) ← observability channel (no raw logging)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/stack/__init__.py` | Create | Package exports |
| `src/apoch/stack/manager.py` | Create | StackManager — orchestrator |
| `src/apoch/stack/registry.py` | Create | Entry-point discovery |
| `src/apoch/stack/component.py` | Create | StackComponent ABC |
| `src/apoch/stack/descriptor.py` | Create | Per-component metadata |
| `src/apoch/stack/manifest.py` | Create | Serialization/deserialization |
| `src/apoch/stack/state.py` | Create | StackState enum (8 states) |
| `src/apoch/stack/events.py` | Create | Event name constants |
| `src/apoch/stack/lock.py` | Create | File-based op lock |
| `src/apoch/stack/result.py` | Create | OperationResult |
| `src/apoch/stack/exceptions.py` | Create | StackError subclasses |
| `src/apoch/stack/paths.py` | Create | StackPaths — all filesystem resolution |
| `src/apoch/stack/clock.py` | Create | ClockProvider — injectable time |
| `src/apoch/stack/runner.py` | Create | CommandRunner — subprocess abstraction |
| `src/apoch/stack/downloader.py` | Create | Downloader — external source abstraction |
| `src/apoch/cli/stack.py` | Create | `apoch stack` subcommand group |
| `src/apoch/cli/install.py` | Modify | Call StackManager.install_all() after MCP config |
| `src/apoch/cli/uninstall.py` | Modify | Call StackManager.uninstall_all() before backup restore |
| `src/apoch/cli/doctor.py` | Modify | Add StackManager.health() check |
| `pyproject.toml` | Modify | Add `apoch.stack.components` entry point group |

## Interfaces / Contracts

```python
# descriptor.py
@dataclass(frozen=True)
class StackDescriptor:
    name: str                    # display name
    kind: ComponentKind          # integrations | store | services
    version: str                 # descriptor API version
    description: str             # one-line summary
    entry_point: str             # python path to component class
    id: str = ""                 # stable identifier (defaults to name)
    dependencies: tuple[str, ...] = ()
    install_command: str = ""    # "npm install -g @fission-ai/openspec@latest"
    install_manager: str = ""    # "npm"
    homepage: str = ""           # project homepage URL
    repository: str = ""         # source repository URL
    docs_url: str = ""           # documentation URL
    requires: tuple[str, ...] = ()  # "node>=20.19.0"
    min_version: str = ""        # minimum supported version
    max_version: str = ""        # maximum supported version
    capabilities: tuple[str, ...] = ()

# component.py
class StackComponent(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> StackDescriptor: ...
    @abstractmethod async def detect(self) -> ComponentInfo: ...
    @abstractmethod async def install(self) -> OperationResult: ...
    @abstractmethod async def verify(self) -> OperationResult: ...
    @abstractmethod async def activate(self) -> OperationResult: ...
    @abstractmethod async def deactivate(self) -> OperationResult: ...
    @abstractmethod async def uninstall(self) -> OperationResult: ...
    @abstractmethod async def health(self) -> dict: ...

@dataclass(frozen=True)
class ComponentInfo:
    installed: bool
    version: str | None = None
    available_version: str | None = None
    executable_path: Path | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

# result.py
@dataclass
class OperationResult:
    component: str
    operation: str
    duration_seconds: float
    result: Literal["success", "partial", "failed"]
    rollback_executed: bool
    errors: list[str]
    warnings: list[str]
    component_state: dict[str, StackState]

# state.py
class StackState(Enum):
    UNKNOWN = "unknown"             # initial / no info
    NOT_INSTALLED = "not_installed" # not found on system
    INSTALLING = "installing"       # installation in progress
    INSTALLED = "installed"         # present and compatible
    ACTIVE = "active"               # installed + configured
    INACTIVE = "inactive"           # installed but disabled
    OUTDATED = "outdated"           # version below min_version
    UNSUPPORTED = "unsupported"     # version above max_version
    BROKEN = "broken"               # integrity verification failed
    ERROR = "error"                 # operation failed
    REMOVED = "removed"             # previously installed, now gone

def derive_state(descriptor, info) -> StackState:
    # Pure function — compares descriptor constraints against
    # observed ComponentInfo. Returns NOT_INSTALLED, INSTALLED,
    # OUTDATED, or UNSUPPORTED.

# clock.py — injectable, mockable
class ClockProvider(ABC):
    @abstractmethod def utcnow(self) -> datetime: ...

# runner.py — subprocess abstraction, mockable
class CommandRunner(ABC):
    @abstractmethod async def run(self, cmd: list[str]) -> RunResult: ...

# downloader.py — source abstraction, mockable
class Downloader(ABC):
    @abstractmethod async def download(self, source: str, dest: Path) -> bool: ...

# paths.py — single source of filesystem truth
@dataclass
class StackPaths:
    config_dir: Path    # ~/.config/apoch
    manifest: Path      # config_dir / stack-manifest.json
    lock: Path          # config_dir / stack.lock
```

## State Machine

Full spec in ``src/apoch/stack/state.py`` module docstring, including
ASCII diagram, transition table, per-state semantics, and flow examples.
Summary below.

### 11 states

| # | State | Meaning |
|---|-------|---------|
| 1 | UNKNOWN | Default — no information available |
| 2 | NOT_INSTALLED | Not found on the system |
| 3 | INSTALLING | Installation in progress |
| 4 | INSTALLED | Present, compatible version |
| 5 | ACTIVE | Installed and configured for use |
| 6 | INACTIVE | Installed but disabled |
| 7 | OUTDATED | Version below ``min_version`` (detect-derived) |
| 8 | UNSUPPORTED | Version above ``max_version`` (detect-derived) |
| 9 | BROKEN | Integrity verification failed |
| 10 | ERROR | Operation failed |
| 11 | REMOVED | Previously installed, now removed |

### Transition arrows

```
UNKNOWN → NOT_INSTALLED
NOT_INSTALLED → INSTALLING
INSTALLING → INSTALLED | ERROR
INSTALLED → ACTIVE | ERROR | REMOVED | OUTDATED | BROKEN
ACTIVE → INACTIVE | ERROR
INACTIVE → INSTALLED
OUTDATED → INSTALLED | ERROR
UNSUPPORTED → ERROR
BROKEN → INSTALLED | ERROR
ERROR → NOT_INSTALLED
REMOVED → UNKNOWN
```

### Layer separation (PR4.1)

State derivation follows a strict three-layer pipeline to separate
concerns:

```
StackDescriptor (declarative — what SHOULD exist)
       │
       ▼  passed to derive_state()
ComponentInfo (factual — what DOES exist, from detect())
       │
       ▼
StackState (decision — what it means)
```

* ``StackDescriptor`` is static metadata (name, version range,
  dependencies, install method).  Never changes at runtime.
* ``ComponentInfo`` is the raw observation from ``detect()`` —
  installed flag, version string, executable path, metadata dict.
  ``detect()`` never infers state.
* ``derive_state(descriptor, info)`` is a **pure function** with no
  I/O or side effects.  It applies the descriptor's version constraints
  to the observed info and produces one of four states:
  ``NOT_INSTALLED``, ``INSTALLED``, ``OUTDATED``, ``UNSUPPORTED``.

The ``StackManager.verify()`` method calls this pipeline before running
the component's own ``verify()`` — so state reflects reality before
the integrity check runs.

### ERROR vs BROKEN vs OUTDATED vs UNSUPPORTED

| State | Source | Component works? | Action |
|-------|--------|------------------|--------|
| ERROR | Failed operation | Maybe | Retry |
| BROKEN | Failed verify | No | Repair |
| OUTDATED | derive_state() (below min) | Yes, limited | Update |
| UNSUPPORTED | derive_state() (above max) | Maybe | Upgrade platform |

## Component Relationships

- **StackManager** receives `StackRegistry`, `FileLock`, `ClockProvider`, `EventBus` via constructor injection. Orchestrates via `StackComponent` interface only.
- **StackRegistry** scans `importlib.metadata.entry_points(group="apoch.stack.components")` at startup → `dict[str, StackComponent]`.
- **StackComponent** implementations receive `CommandRunner`, `Downloader`, `ClockProvider` via constructor injection. Zero direct instantiation of other components.
- **StackPaths** is the single source for all filesystem locations — `config_dir`, `manifest`, `lock`. Used by `StackManager`, `FileLock`, and `StackManifest`.
- **StackManifest** at `~/.config/apoch/stack-manifest.json` via `StackPaths.manifest`. Single serialization layer — no `json.load`/`json.dump` elsewhere.
- **Components** registered as entry points. Four built-in: OpenSpec, Engram, Context7, CodeGraph.
- **Update deferred** — `update()` exists on interface but `StackManager.update_all()` is v1 out-of-scope.

## Events

Emitted via `EventBus` (existing `apoch/core/events.py`): `stack.install_started/completed/failed`, `stack.uninstall_started/completed`, `stack.verify_completed(name, status)`, `stack.repair_completed(name, status)`.

## Threat Matrix

N/A — architectural orchestration design. Per-component subprocess concerns handled at component level in tasks phase.

## Testing Strategy

Every component MUST be testable without Internet. All external deps (subprocess, network, filesystem, clock) replaceable via mocks/fakes.

| Layer | Focus | Approach |
|-------|-------|----------|
| Unit | StackState transitions, OperationResult | pytest param-based |
| Unit | StackManager orchestration + rollback | Inject mock ClockProvider + mock components |
| Unit | StackComponent lifecycle | Inject mock CommandRunner, mock Downloader |
| Unit | Manifest serialization + atomicity | tempdir, temp→rename, corruption recovery |
| Unit | FileLock acquire/release/stale | tempdir, timeout, orphan detection |
| Unit | ClockProvider | FakeClock with deterministic utcnow |
| Unit | CommandRunner | MockRunResult, simulate success/failure |
| Unit | Downloader | MockDownloader, simulate sources |
| Integration | Registry discovery, CLI | test entry points, typer CliRunner |

## Migration / Rollout

No migration required — fresh package. Add `apoch.stack.components` entry point group to `pyproject.toml`. Four built-in component implementations ship alongside this PR or as separate follow-ups per the task plan.

## Open Questions

None — spec and proposal are fully determinative.
