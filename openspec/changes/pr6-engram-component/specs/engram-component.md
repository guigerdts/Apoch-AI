# Delta for Core Stack — Engram Component

## ADDED Requirements

### Requirement: Engram Component Registration

The system MUST register an `EngramComponent` via `apoch.stack.components` entry point with `StackDescriptor(id="engram", name="Engram", kind="integrations", version="1.19.0", ...)`. The component MUST be loadable by `StackManager._get_component()` via entry-point resolution.

### Requirement: Engram detect()

Locate `engram` via `shutil.which("engram")` and parse version from `engram version` stdout. Supports formats: `"engram 1.19.0"`, `"v1.19.0"`, `"1.19.0"`.

| Condition | Result |
|-----------|--------|
| `engram` in PATH, valid version | `ComponentInfo(installed=True, version="1.19.0", executable_path=Path(...))` |
| `engram` not in PATH | `ComponentInfo(installed=False)` |
| CLI errors (non-zero, exception) | `ComponentInfo(installed=False, metadata={...})` |
| CLI succeeds but version unparseable | `ComponentInfo(installed=True, version=None)` + log warning |

### Requirement: Version Parser

`_parse_version(stdout: str) -> str | None` MUST use a regex matching `engram X.Y.Z`, `vX.Y.Z`, and `X.Y.Z`. Never crash — log warning and return `None` on unexpected formats.

### Requirement: Engram verify()

Three-phase: detect() → derive_state() → functional check (`engram doctor`).

| State | Behavior |
|-------|----------|
| NOT_INSTALLED | Immediate failure result |
| OUTDATED / UNSUPPORTED | Diagnostic failure result |
| INSTALLED | `engram doctor` succeeds → `OperationResult(success=True)` |
| INSTALLED + integrity fails | `OperationResult(success=False)` → manager sets BROKEN |

### Requirement: Engram install()

- No prerequisites — Engram is a static Go binary with zero runtime dependencies.
- Resolve install command dynamically via `platform.system()`:
  - **Darwin**: `brew install gentleman-programming/tap/engram`
  - **Linux**: `curl -fsSL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_linux_$(uname -m).tar.gz | tar -xz` (or Homebrew if available)
  - **Windows**: `go install github.com/Gentleman-Programming/engram/cmd/engram@latest`
- Execute the platform-appropriate command via `CommandRunner`
- Post-install → run `self.detect()` to confirm
- Return `OperationResult(success=True/False, ...)`

### Requirement: Engram uninstall()

Engram is a single binary (no package manager tracking). Uninstall strategy:

- **Homebrew path**: `brew uninstall engram`
- **Binary path**: Delete the binary found at `executable_path` + data directory `~/.engram/` (with user confirmation for data dir)
- **Windows**: `go clean -i github.com/Gentleman-Programming/engram/cmd/engram`

Run `self.detect()` to confirm removal. Return `OperationResult`.

### Requirement: Engram activate() / deactivate()

| Method | Behavior |
|--------|----------|
| `activate()` | Run `self.detect()`, return `OperationResult(success=installed)` |
| `deactivate()` | Always return `OperationResult(success=True)` — CLI binary, no session state |

### Requirement: Engram health()

1. Call `self.detect()`
2. If not installed → `{"status": "down", "component": "engram"}`
3. Run `engram doctor` via CommandRunner — the official read-only diagnostic command
4. Success (exit code 0) → `{"status": "healthy"}`
5. Failure (non-zero exit) → `{"status": "degraded", "diagnostics": {...}}`

Do NOT use `engram stats` as a health check — it reports memory statistics, not system health.

### Requirement: Error Handling

All CLI failures MUST return `OperationResult` with descriptive messages. Missing Engram binary, failed Homebrew install, download failures, and unexpected CLI output MUST be handled gracefully.
