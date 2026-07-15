# Delta for cli-interface

## ADDED Requirements

### Requirement: Stack Subcommands

The system SHALL provide an `apoch stack` subcommand namespace for Core Stack lifecycle. Stack commands reuse StackManager/StackRegistry — no code duplication.

#### Scenario: Stack install

- GIVEN a clean system, no Core Stack components installed
- WHEN the user runs `apoch stack install`
- THEN all four components install in registration order
- THEN `verify()` runs after each install
- AND per-component status is reported

#### Scenario: Stack status

- GIVEN components in mixed states (some INSTALLED, one BROKEN)
- WHEN the user runs `apoch stack status`
- THEN output shows per-component state (name, version, status)
- AND BROKEN components SHALL include remediation hints

#### Scenario: Stack uninstall

- GIVEN all four components INSTALLED
- WHEN the user runs `apoch stack uninstall`
- THEN components uninstall in reverse order
- THEN state file is removed
- AND output confirms each removal

#### Scenario: Stack repair

- GIVEN one or more components BROKEN
- WHEN the user runs `apoch stack repair`
- THEN detect() identifies BROKEN components
- THEN repair() runs on each
- AND per-component repair result is reported

## MODIFIED Requirements

### Requirement: Install Module

The system SHALL install Apoch-AI or a specific module, configuring the OpenCode integration. On fresh installs, it SHALL also install Core Stack components after module configuration.
(Previously: installs only Apoch-AI modules and MCP server config)

#### Scenario: Successful fresh install

- GIVEN a clean environment with no prior Apoch-AI installation
- WHEN the user runs `apoch install`
- THEN opencode.json is backed up (even if empty)
- THEN the user sees a diff of proposed changes
- THEN (on consent) opencode.json is updated with MCP config
- THEN the MCP gateway starts and passes health check
- THEN Core Stack components install after module config
- AND all components reach INSTALLED state

#### Scenario: Install when OpenCode is not detected

- GIVEN no OpenCode installation detected
- WHEN the user runs `apoch install`
- THEN the system warns OpenCode was not found
- THEN modules and config install for future use
- THEN Core Stack still installs
- AND exit code is 0 (success with warning)

#### Scenario: User declines consent during install

- GIVEN a diff of proposed opencode.json changes
- WHEN the user responds `n` to consent prompt
- THEN opencode.json is NOT modified
- THEN MCP gateway does NOT start
- THEN Core Stack does NOT install
- AND system prints "Install aborted — no changes made"

#### Scenario: Install without prior MCP configuration

- GIVEN no existing MCP servers entry in opencode.json
- WHEN `apoch install` executes
- THEN a new `mcpServers` key is created
- AND the `apoch` entry is added under `mcpServers`

#### Scenario: Install when MCP server already exists

- GIVEN an opencode.json with existing MCP servers
- WHEN `apoch install` executes
- THEN existing MCP servers are preserved
- AND the `apoch` entry is added alongside them

### Requirement: Doctor Diagnostics

The system SHOULD run diagnostic checks including Core Stack health, and report in human-readable format.
(Previously: MCP gateway and dependency checks only)

#### Scenario: All checks pass

- GIVEN healthy Apoch-AI installation with all Core Stack components INSTALLED
- WHEN the user runs `apoch doctor`
- THEN each check shows `✓` prefix
- AND exit code is 0

#### Scenario: One or more checks fail

- GIVEN a broken MCP gateway or missing Core Stack component
- WHEN the user runs `apoch doctor`
- THEN each failing check shows `✗` with explanation
- THEN BROKEN/UNSUPPORTED stack components SHALL be flagged
- AND exit code is 1
