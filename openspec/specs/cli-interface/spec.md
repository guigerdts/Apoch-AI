# CLI Interface Specification

## Objective

Provide a cross-platform CLI command (`apoch`) as the primary user-facing entry point for installing, managing, and diagnosing Apoch-AI modules and their agent integration.

## Responsibilities

- Implement all `apoch` subcommands: `install`, `uninstall`, `list`, `status`, `mcp`, `config`, `doctor`
- Manage `opencode.json` configuration (backup → diff → consent → modify → rollback)
- Validate system prerequisites before installation
- Report module status and system health in human-readable format
- Provide `--help` and `--version` at every command level

## Scope

### In Scope
- CLI using typer (Python 3.13+ native CLI framework)
- Subcommands: install, uninstall, list, status, mcp, config, doctor
- Terminal output with consistent formatting (colors, tables, exit codes)
- opencode.json mutation lifecycle (backup, diff, consent, modify, rollback)
- Cross-platform compatibility: Linux, macOS, Windows, WSL2, Termux
- `$EDITOR` support for `apoch config edit`

### Out of Scope
- TUI dashboard (future module)
- GUI installer
- Package manager functionality beyond `apoch` itself
- Remote or network-based module registry browsing

## Architecture

CLI is a thin shell that translates terminal arguments into Core API calls. No business logic lives in CLI handlers — they delegate to `ModuleRegistry`, `ConfigManager`, `MCPGateway`, and `AdapterManager`.

```
apoch install → CLI handler → ModuleConfigManager.install()
apoch list   → CLI handler → ModuleRegistry.discover()
apoch status → CLI handler → MCPGateway.health() + ModuleRegistry.stats()
```

### Subcommand Matrix

| Subcommand | Core API | Description |
|------------|----------|-------------|
| `install` | `ModuleConfigManager.install()` | Set up module, configure opencode.json |
| `uninstall` | `ModuleConfigManager.uninstall()` | Remove config, restore backup |
| `list` | `ModuleRegistry.discover()` | List discovered modules and state |
| `status` | `MCPGateway.status()` | Gateway and module health |
| `mcp` | `MCPGateway.start/stop/restart` | Manage MCP server process |
| `config` | `ConfigManager.get/set/edit` | View or edit Apoch-AI config |
| `doctor` | `Diagnostics.run()` | System diagnostics and checks |

## Public Interfaces

```bash
apoch install [--module MODULE]         # Install Apoch-AI or a specific module
apoch uninstall [--module MODULE]       # Remove Apoch-AI or a specific module
apoch list [--verbose]                  # List all modules and their states
apoch status [--format {text,json}]     # System health and gateway status
apoch mcp {start|stop|restart|logs}     # Manage the MCP server
apoch config {get|set|edit|path}        # Configuration management
apoch doctor                            # Run diagnostic checks
apoch --version                         # Print version
apoch --help                            # Print help
```

## Execution Flow: `apoch install`

1. Validate prerequisites (Python 3.13+, uv, platform compatibility)
2. Read current `opencode.json` and create a timestamped backup
3. Compute diff between current and desired configuration
4. Present diff to user with `[Y/n]` consent prompt
5. On consent: write modified `opencode.json`, install MCP server config
6. Start MCP gateway and verify connectivity
7. Report success with module list
8. On decline: do not modify, report abort

## Execution Flow: `apoch uninstall`

1. Locate backup from install step (or latest)
2. Restore `opencode.json` to pre-install state
3. Remove MCP server configuration from opencode.json
4. Stop MCP gateway if running
5. Report success; if no backup exists, warn and offer manual cleanup guidance

## Dependencies

- **Internal**: ModuleRegistry, ConfigManager, MCPGateway, Diagnostics
- **External**: typer (CLI), pyyaml (config), Python `shutil`/`os` (file ops), Python stdlib `json` (opencode.json)

## Requirements

### Requirement: Install Module

The system SHALL install Apoch-AI or a specific module, configuring the OpenCode integration.

#### Scenario: Successful fresh install

- GIVEN a clean environment with no prior Apoch-AI installation
- WHEN the user runs `apoch install`
- THEN opencode.json MUST be backed up (even if empty)
- THEN the user MUST be shown a diff of proposed changes
- THEN (on consent) opencode.json MUST be updated with MCP server configuration
- THEN the MCP gateway MUST start and respond to a health check

#### Scenario: Install when OpenCode is not detected

- GIVEN an environment where OpenCode is not installed or configured
- WHEN the user runs `apoch install`
- THEN the system MUST warn that OpenCode was not found
- THEN the system MUST still install modules and config for later use
- AND the exit code MUST be 0 (success with warning)

#### Scenario: User declines consent during install

- GIVEN a diff of proposed opencode.json changes displayed to user
- WHEN the user responds `n` to the consent prompt
- THEN opencode.json MUST NOT be modified
- THEN the MCP gateway MUST NOT start
- AND the system MUST print "Install aborted — no changes made"

#### Scenario: Install without prior MCP configuration

- GIVEN no existing MCP servers entry in opencode.json
- WHEN `apoch install` executes
- THEN a new `mcpServers` key MUST be created in opencode.json
- AND the `apoch` entry MUST be added under `mcpServers`

#### Scenario: Install when an MCP server already exists

- GIVEN an opencode.json with existing MCP servers
- WHEN `apoch install` executes
- THEN the existing MCP servers MUST be preserved
- AND the `apoch` entry MUST be added alongside them

### Requirement: List Modules

The system MUST list discovered modules with their status.

#### Scenario: List modules with mixed states

- GIVEN a system with Chronicle enabled, Vision disabled, Guardian failed
- WHEN the user runs `apoch list`
- THEN output MUST show three rows with name, version, status
- AND the status column MUST show `running`, `disabled`, or `failed` respectively
- AND exit code MUST be 0

#### Scenario: List with --verbose flag

- GIVEN `apoch list --verbose` is called
- THEN output MUST additionally show config path, entry point, and uptime for running modules

### Requirement: Doctor Diagnostics

The system SHOULD run diagnostic checks and report results in a human-readable format.

#### Scenario: All checks pass

- GIVEN a healthy Apoch-AI installation
- WHEN the user runs `apoch doctor`
- THEN each check MUST show a `✓` prefix
- AND exit code MUST be 0

#### Scenario: One or more checks fail

- GIVEN a broken MCP gateway or missing dependency
- WHEN the user runs `apoch doctor`
- THEN each failing check MUST show a `✗` prefix with explanation
- AND exit code MUST be 1

## Error Cases

| Condition | Behavior |
|-----------|----------|
| opencode.json not writable | Print path and permission error; abort with exit code 1 |
| Consent prompt declined | No changes made; exit code 0 with abort message |
| MCP gateway fails health check | Report failure, suggest `apoch doctor`, keep config applied |
| No backup found on uninstall | Warn user, offer manual cleanup guide, exit code 0 |
| Unknown subcommand | Print error, show help, exit code 2 |
| Config file unreadable | Print path and error, suggest `apoch doctor`, exit code 1 |
| Uninstall removes another tool's MCP config | Validate backup diff; refuse if backup does not match current state |

## Acceptance Criteria

- [ ] `apoch --help` and all subcommand `--help` print non-empty output
- [ ] `apoch install` creates backup, shows diff, asks consent, applies change
- [ ] `apoch uninstall` restores opencode.json from backup
- [ ] `apoch list` shows all modules with correct status labels
- [ ] `apoch status --format json` returns parseable JSON
- [ ] `apoch doctor` detects and reports a broken MCP gateway
- [ ] Exit codes follow convention: 0 success, 1 runtime error, 2 usage error

## Risks

| Risk | Mitigation |
|------|------------|
| User overwrites opencode.json between install and uninstall | Validate backup matches current state before revert |
| Cross-platform path differences | Use `pathlib` and platform detection consistently |
| Colors/ANSI unsupported on Windows terminal | Detect terminal capabilities; fall back to plain text |

## Future Considerations

- Tab-completion scripts for bash, zsh, fish
- `--yes` / `--no-interactive` flag for scripting
- JSON output mode for all subcommands (machine-readable)
- Progress bars for long operations (e.g., `uv tool install`)
