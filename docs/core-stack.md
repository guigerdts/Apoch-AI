# Core Stack Reference

The Core Stack manages installation and lifecycle of third-party developer tooling. It is **frozen** — no architectural changes are permitted. All four adapters are in `src/apoch/stack/components/`.

---

## StackComponent Interface

`StackComponent` (`src/apoch/stack/component.py:51`) is the abstract base that every adapter implements. All lifecycle methods are async for I/O-bound operations.

| Method | Signature | Returns | Purpose |
|--------|-----------|---------|---------|
| `descriptor` | `@property` → `StackDescriptor` | `StackDescriptor` | Static metadata (id, name, version, URLs, etc.) |
| `detect` | `async → ComponentInfo` | `ComponentInfo` | Inspect local system — binary, version, path |
| `install` | `async → OperationResult` | `OperationResult` | Install the component via package manager |
| `uninstall` | `async → OperationResult` | `OperationResult` | Uninstall the component |
| `verify` | `async (*, skip_async=False) → OperationResult` | `OperationResult` | Check correct installation |
| `activate` | `async → OperationResult` | `OperationResult` | Configure/activate for the session |
| `deactivate` | `async → OperationResult` | `OperationResult` | Deactivate without uninstalling |
| `health` | `async → dict` | `dict` | Functional check — "does it actually work?" |

The `health()` return dict must contain at least a `"status"` key with one of `"healthy"`, `"degraded"`, or `"down"`.

---

## ComponentInfo

`ComponentInfo` (`src/apoch/stack/component.py:24`) is a frozen dataclass returned by `detect()`. It contains only factual observation — state derivation is the `StackManager`'s responsibility.

| Field | Type | Description |
|-------|------|-------------|
| `installed` | `bool` | Whether the component is present on the system |
| `version` | `str \| None` | Installed version string |
| `available_version` | `str \| None` | Latest available version (for OUTDATED detection) |
| `executable_path` | `Path \| None` | Path to the component's executable |
| `detected_at` | `datetime \| None` | Timestamp of last `detect()` call |
| `metadata` | `Mapping[str, Any]` | Additional free-form observations |

---

## ComponentStatus

`ComponentStatus` (`src/apoch/stack/manager.py:30`) is a mutable dataclass representing the manager's view of a component at runtime.

| Field | Type | Default |
|-------|------|---------|
| `descriptor` | `StackDescriptor` | (required) |
| `state` | `StackState` | `UNKNOWN` |
| `info` | `ComponentInfo \| None` | `None` |

---

## StackState

`StackState` (`src/apoch/stack/state.py:250`) is an enum with 11 values that form the FSM. Every state transition is validated against `_TRANSITIONS`.

| State | Value | Meaning |
|-------|-------|---------|
| `UNKNOWN` | `"unknown"` | No information available — initial default |
| `NOT_INSTALLED` | `"not_installed"` | Not found on the system |
| `INSTALLING` | `"installing"` | Installation in progress |
| `INSTALLED` | `"installed"` | Present and compatible version |
| `ACTIVE` | `"active"` | Installed and configured for use |
| `INACTIVE` | `"inactive"` | Installed but disabled |
| `OUTDATED` | `"outdated"` | Version below minimum required |
| `UNSUPPORTED` | `"unsupported"` | Version exceeds maximum supported |
| `BROKEN` | `"broken"` | Installed but verification failed |
| `ERROR` | `"error"` | Unexpected failure during an operation |
| `REMOVED` | `"removed"` | Previously installed, now removed |

### State Machine — Valid Transitions

```
UNKNOWN ──────────────→ NOT_INSTALLED
NOT_INSTALLED ─────────→ INSTALLING
INSTALLING ────────────→ INSTALLED | ERROR
INSTALLED ─────────────→ ACTIVE | ERROR | REMOVED | OUTDATED | BROKEN
ACTIVE ────────────────→ INACTIVE | ERROR
INACTIVE ──────────────→ INSTALLED
OUTDATED ──────────────→ INSTALLED | ERROR
UNSUPPORTED ───────────→ ERROR
BROKEN ────────────────→ INSTALLED | ERROR
ERROR ─────────────────→ NOT_INSTALLED
REMOVED ───────────────→ UNKNOWN
```

Formal transition table (`_TRANSITIONS` in `src/apoch/stack/state.py:304`):

| From | To |
|------|----|
| `UNKNOWN` | `NOT_INSTALLED` |
| `NOT_INSTALLED` | `INSTALLING` |
| `INSTALLING` | `INSTALLED`, `ERROR` |
| `INSTALLED` | `ACTIVE`, `ERROR`, `REMOVED`, `OUTDATED`, `BROKEN` |
| `ACTIVE` | `INACTIVE`, `ERROR` |
| `INACTIVE` | `INSTALLED` |
| `OUTDATED` | `INSTALLED`, `ERROR` |
| `UNSUPPORTED` | `ERROR` |
| `BROKEN` | `INSTALLED`, `ERROR` |
| `ERROR` | `NOT_INSTALLED` |
| `REMOVED` | `UNKNOWN` |

### Distinguishing the Four Diagnostic States

| State | Set by | Component works? | Action | Resolution |
|-------|--------|-------------------|--------|------------|
| `ERROR` | Operation | Maybe | Retry | Retry the operation |
| `BROKEN` | Verify | No | Repair | Fix integrity |
| `OUTDATED` | `detect()` | Yes (limited) | Update | Update component |
| `UNSUPPORTED` | `detect()` | Maybe | — | Upgrade platform |

---

## derive_state()

`derive_state()` (`src/apoch/stack/state.py:341`) is a **pure function** — no I/O, no side effects. It compares a `StackDescriptor`'s version constraints against observed `ComponentInfo`.

| Condition | Returns |
|-----------|---------|
| `not info.installed` | `NOT_INSTALLED` |
| `info.version` is `None` or unparseable | `NOT_INSTALLED` |
| `version < min_version` | `OUTDATED` |
| `version > max_version` | `UNSUPPORTED` |
| Otherwise | `INSTALLED` |

`min_version` is evaluated **before** `max_version` — a component below min AND above max reports `OUTDATED`, never `UNSUPPORTED`.

---

## StackManager

`StackManager` (`src/apoch/stack/manager.py:38`) is the lifecycle orchestrator. It registers components, tracks status, resolves dependencies, and drives lifecycle operations.

### Constructor

```python
StackManager(registry: StackRegistry, *, emit_event: Callable | None = None)
```

- `registry`: `StackRegistry` containing component descriptors
- `emit_event`: Optional callback for lifecycle events `(event_type, component_name, details_dict)`

### Public Methods

| Method | Async | Signature | Description |
|--------|-------|-----------|-------------|
| `register_instance` | No | `(name, component)` | Register a pre-created instance (testing) |
| `get_status` | No | `(component_name) → ComponentStatus` | Return current status |
| `list_components` | No | `() → dict[str, ComponentStatus]` | Snapshot of every known component |
| `refresh` | Yes | `(component_name=None)` | Re-detect one or all components |
| `refresh_sync` | No | `(component_name=None)` | Synchronous wrapper around `refresh()` |
| `install` | Yes | `(component_name) → OperationResult` | Install + dependencies |
| `uninstall` | Yes | `(component_name) → OperationResult` | Uninstall (idempotent) |
| `verify` | Yes | `(component_name, *, skip_async=False) → OperationResult` | Detect + derive + verify |
| `install_all` | Yes | `() → list[OperationResult]` | All in registration order (rolls back on failure) |
| `uninstall_all` | Yes | `() → list[OperationResult]` | All in reverse order |

### Factory

`create_manager()` (`src/apoch/stack/factory.py:14`) wires a fresh `StackManager`:

```python
def create_manager() -> StackManager:
    registry = StackRegistry()
    registry.discover()
    return StackManager(registry)
```

Safe to call repeatedly — no global state.

---

## CommandRunner Hierarchy

`CommandRunner` (`src/apoch/stack/runner.py:40`) provides subprocess isolation. Components never execute subprocesses directly.

```
CommandRunner (ABC)          ← Abstract base
  ├── RealRunner             ← asyncio.create_subprocess_exec (production)
  └── MockRunner             ← Configurable test double (tests)
```

### RunResult

| Field | Type | Description |
|-------|------|-------------|
| `returncode` | `int` | Process exit code |
| `stdout` | `str` | Captured standard output |
| `stderr` | `str` | Captured standard error |
| `duration` | `float` | Wall-clock seconds |
| `success` | `bool` | `returncode == 0` (property) |

### RealRunner

Uses `asyncio.create_subprocess_exec` with `asyncio.wait_for` for optional timeouts. Handles `TimeoutError` and `FileNotFoundError` gracefully.

### MockRunner

Returns a configurable `RunResult` — used in all 401 stack tests:

```python
runner = MockRunner(result=RunResult(returncode=0, stdout="1.0.0"))
component = MyComponent(runner=runner)
```

---

## StackDescriptor

`StackDescriptor` (`src/apoch/stack/descriptor.py:15`) is an immutable frozen dataclass.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Stable machine-readable identifier (e.g. `"openspec"`) |
| `name` | `str` | Short display name (e.g. `"OpenSpec"`) |
| `kind` | `ComponentKind` | Category: `"integrations"`, `"store"`, `"services"` |
| `version` | `str` | Descriptor API version (not the installed tool version) |
| `description` | `str` | One-line human-readable description |
| `entry_point` | `str` | Python path to `StackComponent` subclass |
| `dependencies` | `tuple[str, ...]` | Names of components that must be installed first |
| `install_command` | `str` | Official install command (e.g. `"npm install -g ..."`) |
| `install_manager` | `str` | Package manager name (`"npm"`, `"homebrew"`, etc.) |
| `homepage` | `str` | Project homepage URL |
| `repository` | `str` | Source repository URL |
| `docs_url` | `str` | Documentation URL |
| `requires` | `tuple[str, ...]` | Prerequisites (e.g. `"node>=20.19.0"`) |
| `min_version` | `str` | Minimum supported version (inclusive) |
| `max_version` | `str` | Maximum supported version (inclusive) |
| `capabilities` | `tuple[str, ...]` | Features the component exposes |

---

## StackRegistry

`StackRegistry` (`src/apoch/stack/registry.py:22`) manages component descriptors using a thread-safe in-memory map.

| Method | Signature | Description |
|--------|-----------|-------------|
| `register` | `(descriptor)` | Register a descriptor (raises `ValueError` on duplicate) |
| `get` | `(name) → StackDescriptor` | Look up by name (raises `StackNotFoundError`) |
| `contains` | `(name) → bool` | Check if registered |
| `list` | `() → tuple[StackDescriptor]` | Snapshot of all descriptors |
| `discover` | `(group="apoch.stack.components") → int` | Discover via `importlib.metadata` entry points |

Discovery scans the `apoch.stack.components` entry-point group (defined in `pyproject.toml` lines 29–33). Invalid entry points are logged and skipped — discovery never aborts.
