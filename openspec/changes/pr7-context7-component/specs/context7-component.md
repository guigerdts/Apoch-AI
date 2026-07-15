# Delta for Core Stack — Context7 Component

## ADDED Requirements

### Requirement: Context7 Component Registration

The system MUST register a `Context7Component` via `apoch.stack.components` entry point with `StackDescriptor(id="context7", name="Context7", kind="integrations", version="0.5.4", ...)`. The component MUST be loadable by `StackManager._get_component()` via entry-point resolution.

### Requirement: Context7 detect()

Locate `ctx7` via `shutil.which("ctx7")` and parse version from `ctx7 --version` stdout. Supports formats: `"0.5.4"`, `"v0.5.4"`, `"ctx7 0.5.4"`.

| Condition | Result |
|-----------|--------|
| `ctx7` in PATH, valid version | `ComponentInfo(installed=True, version="0.5.4", executable_path=Path(...))` |
| `ctx7` not in PATH | `ComponentInfo(installed=False)` |
| CLI errors (non-zero, exception) | `ComponentInfo(installed=False, metadata={...})` |
| CLI succeeds but version unparseable | `ComponentInfo(installed=True, version=None)` + log warning |

### Requirement: Version Parser

`_parse_version(stdout: str) -> str | None` MUST use a regex matching `ctx7 X.Y.Z`, `vX.Y.Z`, and `X.Y.Z`. Never crash — log warning and return `None` on unexpected formats.

### Requirement: Context7 verify()

Two-phase: detect() → derive_state() → functional check (`ctx7 --help`).

**Note**: Context7 does NOT have a `doctor` command (verified from official docs and CLI source). The `--help` flag serves as the basic responsiveness check.

| State | Behavior |
|-------|----------|
| NOT_INSTALLED | Immediate failure result |
| OUTDATED / UNSUPPORTED | Diagnostic failure result |
| INSTALLED | `ctx7 --help` succeeds → `OperationResult(success=True)` |
| INSTALLED + help fails | `OperationResult(success=False)` → manager sets BROKEN |

### Requirement: Context7 install()

- Prerequisite: none explicit at CLI level — `npm` handles Node.js requirements. The DESCRIPTOR documents `node>=18` in `requires`.
- Execute `npm install -g ctx7` via CommandRunner
- Post-install → run `self.detect()` to confirm
- Return `OperationResult(success=True/False, ...)`

### Requirement: Context7 uninstall()

- Execute `npm uninstall -g ctx7` via CommandRunner
- If already not installed → return `OperationResult(success=True)` (npm semantics: uninstalling a missing package is a no-op, not an error)
- Post-uninstall → run `self.detect()` to confirm removal
- Return `OperationResult(success=True/False, ...)`

### Requirement: Context7 activate() / deactivate()

| Method | Behavior |
|--------|----------|
| `activate()` | Run `self.detect()`, return `OperationResult(success=installed)` |
| `deactivate()` | Always return `OperationResult(success=True)` — CLI binary, no session state |

### Requirement: Context7 health()

1. Call `self.detect()`
2. If not installed → `{"status": "down", "component": "context7"}`
3. Binary found + version parsed → `{"status": "healthy"}`
4. Binary found but version unparseable → `{"status": "degraded", "diagnostics": {"error": "version parse failed"}}`

**Note**: Context7 has no `doctor` or health CLI command. The health check is shallower than OpenSpec's (which uses `openspec doctor --json`) and Engram's (which uses `engram doctor`). This is a documented architectural limitation of the upstream CLI — the health endpoint (`/api/health`) only exists for enterprise Docker deployments.

### Requirement: Error Handling

All CLI failures MUST return `OperationResult` with descriptive messages. Missing ctx7 binary, failed npm install, network errors, and unexpected CLI output MUST be handled gracefully.
