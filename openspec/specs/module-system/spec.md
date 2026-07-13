# Module System Specification

## Objective

Provide a pluggable module discovery and lifecycle framework where Apoch-AI capabilities can be installed, activated, configured, and deactivated independently — without the Core depending on any specific module.

## Responsibilities

- Discover installed modules via Python entry points
- Manage module lifecycle: `init(config) → start(ctx) → stop() → shutdown()`
- Apply per-module YAML config overrides from a canonical config file
- Enforce per-module exception boundaries so no module crash propagates
- Provide an ABC (`Module`) as the contract between Core and modules

## Scope

### In Scope
- Entry point discovery via `importlib.metadata.entry_points` group `apoch.modules`
- Lifecycle ABC with four phases
- Config override mechanism (YAML file at `~/.config/apoch/config.yaml` or `$APOCH_CONFIG`)
- Per-module exception isolation (try/except guard around each lifecycle call)
- Enable/disable state per module
- Module metadata (name, version, description, dependencies)
- Plugin mechanism shares the same lifecycle ABC but uses a separate entry point group `apoch.plugins`

### Out of Scope
- Plugin marketplace or remote registry
- Dynamic hot-reload of modules
- Module dependency resolution and ordering beyond simple enable/disable
- Per-module process isolation (future concern)

## Architecture

The Module System sits at the Core of Apoch-AI. A `ModuleRegistry` scans entry points at startup, instantiates each module that is not explicitly disabled, and drives its lifecycle.

```
Core → ModuleRegistry → [Module ABC instances]
                           ├── Chronicle
                           ├── Guardian
                           └── Vision
```

Each module instance is wrapped in an exception boundary. Module ABC guarantees `init → start → stop → shutdown` ordering. Config overrides are merged: defaults from the module, then user overrides from YAML.

## Public Interfaces

### `Module` ABC

```python
class Module(ABC):
    metadata: ModuleMetadata  # name, version, description

    def __init__(self, config: dict) -> None: ...
    async def start(self, context: Context) -> None: ...
    async def stop(self) -> None: ...
    async def shutdown(self) -> None: ...
```

### `ModuleRegistry`

```python
class ModuleRegistry:
    def discover(self) -> list[ModuleMetadata]: ...
    def load(self, name: str) -> Module: ...
    def start_all(self, context: Context) -> None: ...
    def stop_all(self) -> None: ...
```

## Execution Flow

1. CLI or Core triggers `ModuleRegistry.discover()` → scans `apoch.modules` entry points
2. For each discovered module not explicitly disabled in config: instantiate via `load(name)`, call `init(config)`, register in registry
3. `start_all(context)` → for each loaded module, call `module.start(ctx)` inside try/except
4. On shutdown: `stop_all()` → for each running module, call `module.stop()`, then `module.shutdown()` — reverse order from init
5. If any `start()` raises, Guardian captures and logs the exception; the other modules continue unaffected

## Dependencies

- **Internal**: Guardian (exception capture), Chronicle (activity recording)
- **External**: Python `importlib.metadata` (stdlib), PyYAML for config parsing

## Requirements

### Requirement: Entry Point Discovery

The system MUST discover all installed modules registered under the `apoch.modules` entry point group.

#### Scenario: Discover modules with valid entry points

- GIVEN a Python environment with packages installed that register `apoch.modules` entry points
- WHEN `ModuleRegistry.discover()` is called
- THEN it MUST return a non-empty list of `ModuleMetadata` objects
- AND each entry MUST contain `name`, `version`, and `description`

#### Scenario: Discover modules when none are registered

- GIVEN a Python environment with zero packages registering `apoch.modules`
- WHEN `ModuleRegistry.discover()` is called
- THEN it MUST return an empty list

#### Scenario: Entry point resolution failure

- GIVEN a package registered with `apoch.modules` whose entry point module cannot be imported
- WHEN `ModuleRegistry.load(name)` is called
- THEN it MUST raise `ModuleLoadError`
- AND the error MUST be logged before propagating

### Requirement: Lifecycle Contract

Each module MUST implement `Module` ABC with the four lifecycle methods and respect their invocation ordering.

#### Scenario: Full lifecycle success

- GIVEN a module with valid `init`, `start`, `stop`, `shutdown` implementations
- WHEN the Core drives `init → start → stop → shutdown` in sequence
- THEN each method MUST complete without raising

#### Scenario: Start called before init

- GIVEN a module instance
- WHEN `start()` is called before `init(config)`
- THEN the system MUST raise `LifecycleError`
- AND the module MUST NOT transition to the `running` state

#### Scenario: Exception during module start

- GIVEN a module whose `start()` raises `RuntimeError`
- WHEN `start()` is invoked inside the registry's exception boundary
- THEN the registry MUST catch the exception
- AND the module MUST transition to the `failed` state
- AND other modules MUST continue unaffected

### Requirement: Config Override

The system MUST merge per-module YAML config overrides from a canonical config file on top of each module's default config.

#### Scenario: Config merge with user overrides

- GIVEN a module with default config `{"log_level": "info"}` and a user config file containing `{"log_level": "debug"}`
- WHEN the module is initialized
- THEN the effective config MUST be `{"log_level": "debug"}` (user override wins)

#### Scenario: Config file missing

- GIVEN no config file exists and no `$APOCH_CONFIG` is set
- WHEN any module is initialized
- THEN each module MUST receive its default config

### Requirement: Enable/Disable State

The system MUST honor per-module enable/disable state from the config file. Disabled modules MUST NOT be loaded or started.

#### Scenario: Module disabled in config

- GIVEN a configuration with `modules.chronicle.enabled: false`
- WHEN `ModuleRegistry.discover()` returns Chronicle among discovered modules
- THEN `ModuleRegistry.start_all()` MUST NOT call `Chronicle.start()`
- AND Chronicle MUST appear in `list` output with status `disabled`

#### Scenario: Module re-enabled after disable

- GIVEN a previously disabled module whose config is now set to `enabled: true`
- WHEN `ModuleRegistry.discover()` is called during next startup
- THEN the module MUST be loaded and started normally

## Error Cases

| Condition | Behavior |
|-----------|----------|
| Entry point module cannot be imported | `ModuleLoadError` raised and logged; module skipped |
| Module `start()` raises | Exception caught by boundary; module set to `failed` state; other modules continue |
| Config file is malformed YAML | Parse error raised; fallback to empty config with warning |
| Module `stop()` raises | Exception caught and logged; `shutdown()` still called |
| Circular config reference | Ignored with warning; default used |

## Acceptance Criteria

- [ ] Module with valid entry point is discovered on `discover()`
- [ ] Module ABC enforces correct lifecycle ordering at class definition time
- [ ] Module crash in `start()` does not prevent other modules from starting
- [ ] Disabled module is listed but not started
- [ ] User config overrides module defaults for any key
- [ ] Plugins under `apoch.plugins` group follow the same lifecycle independently

## Risks

| Risk | Mitigation |
|------|------------|
| Entry point namespace collision with other tools | Use specific `apoch.modules` group name; document the convention |
| Module blocks `start()` indefinitely | Apply configurable timeout per lifecycle call |
| Config file parse error leaves system unusable | Validate config schema at startup; fall back to defaults |

## Future Considerations

- Per-module health checks and restart policies (circuit breaker pattern)
- Module dependency declaration and load ordering
- Dynamic load/unload without process restart
- Plugin hot-reload for development mode
