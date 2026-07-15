# Delta for Core Stack — OpenSpec Component

## ADDED Requirements

### Requirement: OpenSpec Component Registration

The system MUST register an `OpenSpecComponent` via `apoch.stack.components` entry point with `StackDescriptor(id="openspec", name="OpenSpec", kind="integrations", version="1.0.0", ...)`. The component MUST be loadable by `StackManager._get_component()` via entry-point resolution.

### Requirement: OpenSpec detect()

Locate `openspec` via `shutil.which("openspec")` and parse version from `openspec --version` stdout. Supports formats: `"openspec 1.6.0"`, `"v1.6.0"`, `"1.6.0"`.

| Condition | Result |
|-----------|--------|
| `openspec` in PATH, valid version | `ComponentInfo(installed=True, version="1.6.0", executable_path=Path(...))` |
| `openspec` not in PATH | `ComponentInfo(installed=False)` |
| CLI errors (non-zero, exception) | `ComponentInfo(installed=False, metadata={...})` |
| CLI succeeds but version unparseable | `ComponentInfo(installed=True, version=None)` + log warning |

### Requirement: Version Parser

`_parse_version(stdout: str) -> str | None` MUST use a regex matching `openspec X.Y.Z`, `vX.Y.Z`, and `X.Y.Z`. Never crash — log warning and return `None` on unexpected formats.

### Requirement: OpenSpec verify()

Three-phase: detect() → derive_state() → functional check (`openspec --help`).

| State | Behavior |
|-------|----------|
| NOT_INSTALLED | Immediate failure result |
| OUTDATED / UNSUPPORTED | Diagnostic failure result |
| INSTALLED | `openspec --help` succeeds → `OperationResult(success=True)` |
| INSTALLED + integrity fails | `OperationResult(success=False)` → manager sets BROKEN |

### Requirement: OpenSpec install()

- Prerequisite: check `node --version`, parse semver
- If `node` not found → `OperationResult(success=False, message="node>=20.19.0 required")`
- If `node` < 20.19.0 → `OperationResult(success=False, message="node>=20.19.0 required, found X.Y.Z")`
- On pass → execute `npm install -g @fission-ai/openspec@latest` via CommandRunner
- Post-install → run `self.detect()` to confirm
- Return `OperationResult(success=True/False, ...)`

### Requirement: OpenSpec uninstall()

Execute `npm uninstall -g @fission-ai/openspec` via CommandRunner, then `self.detect()` to confirm removal. Return `OperationResult`.

### Requirement: OpenSpec activate() / deactivate()

| Method | Behavior |
|--------|----------|
| `activate()` | Run `self.detect()`, return `OperationResult(success=installed)` |
| `deactivate()` | Always return `OperationResult(success=True)` — CLI tools, no session state |

### Requirement: OpenSpec health()

1. Call `self.detect()`
2. If not installed → `{"status": "down", "component": "openspec"}`
3. Run `openspec --help` via CommandRunner
4. Success → `{"status": "healthy"}`
5. Failure → `{"status": "degraded", "diagnostics": {...}}`

### Requirement: CLI Enrichment — stack status

`apoch stack status` for OpenSpec MUST display: name + id, state, installed version, homepage, repository, docs URL, install command.

### Requirement: Error Handling

All CLI failures MUST return `OperationResult` with descriptive messages. Network errors during npm install, missing or outdated Node.js, and unexpected CLI output MUST be handled gracefully.
