# Configuration Guide

## Current State

Apoch-AI has **no persistent config file** by default. All configuration uses in-code defaults. The configuration loader (`ConfigLoader`) is wired and ready — but no file is created on install.

---

## How Configuration Works

The `ConfigLoader` (`src/apoch/config/loader.py`) reads from three sources in ascending precedence:

```
Defaults  ←  YAML file  ←  Environment variables
(lowest)                     (highest)
```

### 1. Hardcoded Defaults

| Key | Default | Description |
|-----|---------|-------------|
| `log_level` | `"info"` | Logging verbosity |
| `home` | `None` | Apoch home directory (resolved at runtime) |
| `modules` | `{}` | Per-module configuration overrides |

Source: `src/apoch/config/defaults.py`

### 2. YAML Config File

Place a file at one of these paths:

| Path | Priority |
|------|----------|
| `$APOCH_CONFIG` env var | Highest (file) |
| `~/.config/apoch/config.yaml` | Default |

Example `~/.config/apoch/config.yaml`:

```yaml
log_level: debug
modules:
  guardian:
    enabled: true
```

Unknown keys trigger a warning but do not block loading.

### 3. Environment Variables

| Variable | Maps To | Example |
|----------|---------|---------|
| `APOCH_LOG_LEVEL` | `log_level` | `APOCH_LOG_LEVEL=debug` |
| `APOCH_HOME` | `home` | `APOCH_HOME=/opt/apoch` |

Env vars always win over YAML values.

---

## How Components Are Discovered

Stack components register themselves via Python entry points in `pyproject.toml`:

```toml
[project.entry-points."apoch.stack.components"]
codegraph = "apoch.stack.components.codegraph:CodeGraphComponent"
context7 = "apoch.stack.components.context7:Context7Component"
engram = "apoch.stack.components.engram:EngramComponent"
openspec = "apoch.stack.components.openspec:OpenSpecComponent"
```

`StackRegistry.discover()` scans the `apoch.stack.components` entry-point group using `importlib.metadata` and instantiates each component to read its descriptor. Invalid entry points are logged and skipped — discovery never aborts.

Core modules use the same pattern via `apoch.modules`:

```toml
[project.entry-points."apoch.modules"]
chronicle = "apoch.modules.chronicle.module:ChronicleModule"
guardian = "apoch.modules.guardian.module:GuardianModule"
optimizer = "apoch.modules.optimizer.module:OptimizerModule"
oracle = "apoch.modules.oracle.module:OracleModule"
pulse = "apoch.modules.pulse.module:PulseModule"
vision = "apoch.modules.vision.module:VisionModule"
```

## Adding a Component to the Registry

Add a new entry under the appropriate `[project.entry-points]` group in `pyproject.toml`:

```toml
[project.entry-points."apoch.stack.components"]
my-tool = "apoch.stack.components.my_tool:MyToolComponent"
```

The class must implement the `StackComponent` interface (see `src/apoch/stack/component.py`). After editing, reinstall the package with `uv sync` for the entry point to register.

## Removing a Component

Delete the entry-point line from `pyproject.toml` and run `uv sync`. Components referenced in code but absent from the registry raise `StackNotFoundError` at runtime.

## Roadmap

Planned configuration enhancements (not yet implemented):

- `apoch config init` — scaffold `~/.config/apoch/config.yaml`
- `apoch config get/set` — runtime config read/write
- Stack component-level config overrides in YAML
