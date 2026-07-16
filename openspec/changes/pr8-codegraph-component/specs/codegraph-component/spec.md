# CodeGraph Component Specification

## Purpose

The CodeGraph component adapts the official `codegraph` CLI (`@colbymchenry/codegraph` npm package) as a StackComponent. Apoch does **not** implement CodeGraph — it delegates to the official binary via its public CLI.

## Requirements

### Descriptor

The component MUST export a static `CODEGRAPH_DESCRIPTOR` (`StackDescriptor`) with fixed metadata:

| Field | Value |
|-------|-------|
| `id` | `codegraph` |
| `name` | `CodeGraph` |
| `kind` | `integrations` |
| `version` | `1.4.1` |
| `install_command` | `npm install -g @colbymchenry/codegraph` |
| `install_manager` | `npm` |
| `homepage` | `https://colbymchenry.github.io/codegraph/` |
| `repository` | `https://github.com/colbymchenry/codegraph` |
| `docs_url` | `https://colbymchenry.github.io/codegraph/` |
| `requires` | `("node",)` |
| `capabilities` | `("code-intelligence", "knowledge-graph", "mcp")` |

#### Scenario: Static descriptor is accessible

- GIVEN a `CodeGraphComponent` instance
- WHEN accessing the `descriptor` property
- THEN it MUST return the static `CODEGRAPH_DESCRIPTOR`

### Detection

`detect()` MUST locate the `codegraph` binary via `shutil.which()` and parse its version from `codegraph --version`. The version regex SHALL be `r"(\d+\.\d+\.\d+)"` — bare semver without prefix.

#### Scenario: Binary found and version parsed

- GIVEN `codegraph` is on `$PATH`
- WHEN `detect()` is called
- THEN it MUST return `ComponentInfo(installed=True, version="1.3.1", executable_path=Path(...))`

#### Scenario: Binary not found

- GIVEN `codegraph` is NOT on `$PATH`
- WHEN `detect()` is called
- THEN it MUST return `ComponentInfo(installed=False)`

#### Scenario: Version command fails

- GIVEN the binary exists but `--version` returns non-zero
- WHEN `detect()` is called
- THEN it MUST return `ComponentInfo(installed=False)` with error metadata

### Install

`install()` MUST run `npm install -g @colbymchenry/codegraph` and confirm via `detect()`.

#### Scenario: Successful install

- GIVEN `npm` is available and network is reachable
- WHEN `install()` is called
- THEN it MUST return `OperationResult(success=True, message="CodeGraph <version> installed")`

#### Scenario: Install fails

- GIVEN npm install fails (network, permissions, or non-zero exit)
- WHEN `install()` is called
- THEN it MUST return `OperationResult(success=False)` with error details

### Uninstall

`uninstall()` MUST run `npm uninstall -g @colbymchenry/codegraph` when installed, and MUST return success when already absent.

#### Scenario: Uninstall installed package

- GIVEN CodeGraph is installed
- WHEN `uninstall()` is called
- THEN it MUST run `npm uninstall -g @colbymchenry/codegraph`
- AND return `OperationResult(success=True)`

#### Scenario: Uninstall when not installed

- GIVEN CodeGraph is NOT installed
- WHEN `uninstall()` is called
- THEN it MUST return `OperationResult(success=True, message="... not installed")`

### Verify

`verify()` MUST confirm the binary exists via `detect()` and run `codegraph --help` as a responsiveness check. CodeGraph has no doctor command — this matches the Context7 pattern.

#### Scenario: Verify success

- GIVEN `codegraph` is on `$PATH` and `--help` exits 0
- WHEN `verify()` is called
- THEN it MUST return `OperationResult(success=True)` with version

#### Scenario: Verify fails when not installed

- GIVEN `codegraph` is NOT on `$PATH`
- WHEN `verify()` is called
- THEN it MUST return `OperationResult(success=False, message="... not installed")`

### Health

`health()` MUST run `codegraph status --json`, parse the JSON, and return it as `diagnostics`. Health evaluates ONLY CLI availability — project state (e.g., `.codegraph/` existence) MUST NOT be evaluated.

#### Scenario: Healthy with valid JSON

- GIVEN `codegraph` is installed and `status --json` returns exit 0 with valid JSON
- WHEN `health()` is called
- THEN it MUST return `{"status": "healthy", "version": "1.3.1", "diagnostics": {...}}`

#### Scenario: Down when not installed

- GIVEN `codegraph` is NOT installed
- WHEN `health()` is called
- THEN it MUST return `{"status": "down", "version": None}`

#### Scenario: Graceful JSON parse error

- GIVEN `status --json` returns unparseable output
- WHEN `health()` is called
- THEN it MUST NOT throw — fall back gracefully

### Activate / Deactivate

`activate()` MUST verify binary presence. `deactivate()` MUST be a no-op (CLI binary with no persistent session).

#### Scenario: Activate when installed

- GIVEN `codegraph` is installed
- WHEN `activate()` is called
- THEN it MUST return `OperationResult(success=True)` with version

#### Scenario: Deactivate always succeeds

- GIVEN any state
- WHEN `deactivate()` is called
- THEN it MUST return `OperationResult(success=True)`
