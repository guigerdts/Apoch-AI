# Creating a New Stack Adapter

This guide explains how to add a new component to the Core Stack. Adapters follow the **OpenSpec Reference Component** pattern — copy its structure and change only tool-specific logic.

## Prerequisites

- The target tool must have a documented **public CLI** (binary reachable via `shutil.which`)
- The CLI must support a **version flag** (`--version` or `<subcommand> version`)
- The CLI must accept at least one **read-only command** that returns exit code 0 when operational (`--help`, `doctor`, or similar)
- You must verify all CLI behavior against **official documentation** — never infer

## Step 1: Research the Official CLI

Before writing any code, verify:

| Question | How to verify |
|----------|---------------|
| What is the binary name? | `which <name>`, npm/github docs |
| What is the version command? | `<binary> --version` or `<binary> version` |
| Is there a `doctor` command? | `<binary> doctor` — check docs + changelog |
| What is the install method? | npm, brew, go install, binary download? |
| What is the uninstall method? | npm uninstall, brew uninstall? |
| What are the prerequisites? | Node.js version, Go, etc. |
| Is health check available? | Structured JSON output? Exit code only? |

Document findings in the proposal before implementing.

## Step 2: Create the Adapter File

Copy `src/apoch/stack/components/openspec.py` as a template.

### What stays identical
- Module docstring structure
- Imports (same six modules)
- `__init__(self, runner)` constructor
- `descriptor` property
- `detect()` structure: `which → run → parse → return`
- `activate()` / `deactivate()` — identical across all adapters
- `verify()` structure: `detect → check not installed → run command → return`
- `install()` structure: `run command → detect to confirm → return`
- `uninstall()` structure: `detect → run command → return`
- `health()` structure: `detect → return status dict`

### What to adapt
| Element | How to change |
|---------|---------------|
| `DESCRIPTOR` constant | Tool ID, name, version, install command, URLs |
| Binary name in `shutil.which()` | Replace `"openspec"` with your binary |
| Version command | Replace `["openspec", "--version"]` with your command |
| `_parse_version()` regex | Replace the prefix (e.g. `openspec\s+` → `ctx7\s+`) |
| Install command | Replace `["npm", "install", "-g", ...]` |
| Uninstall command | Replace `["npm", "uninstall", "-g", ...]` |
| Verify command | Replace `["openspec", "doctor"]` with your check command |
| Health strategy | If your tool has no `doctor`, use detect-only (see Context7) |
| `component="..."` string | Your tool's registry ID |
| Log messages | Replace tool name in log strings |

### Handle CLI-specific variance

| Scenario | Example | Approach |
|----------|---------|----------|
| No universal install command | Engram (brew on macOS, go install on Windows) | Use `_get_install_args()` helper with `platform.system()` dispatch |
| No `doctor` command | Context7 | Use `--help` for verify, detect-only for health |
| Different uninstall semantics | Engram returns failure when absent; npm returns success | Match the upstream's semantics |
| Rich health JSON | OpenSpec (`--json` flag) | Try JSON parse, fallback to exit code |
| Binary path analysis | Engram uninstall (Homebrew vs manual) | Inspect `executable_path` |

## Step 3: Register the Component

1. Add export to `src/apoch/stack/components/__init__.py`
2. Add entry point in `pyproject.toml` under `[project.entry-points."apoch.stack.components"]`
3. Verify: `python -c "from importlib.metadata import entry_points; eps = entry_points(group='apoch.stack.components'); print([ep.name for ep in eps])"`

## Step 4: Write Tests

Copy `tests/stack/components/test_openspec.py` as a template.

### Required test coverage
- DESCRIPTOR fields (id, name, kind, version, install_command, etc.)
- Version parser: prefix, v-prefix, bare, multiline, nonsense, empty
- Component: descriptor, default runner, custom runner injection
- Entry point resolution
- `detect()`: not found, success, CLI error, version unparseable
- `install()`: success, failure, binary not found after install
- `verify()`: not installed, success, check command fails
- `health()`: healthy, degraded, down
- `activate()`: installed, not installed
- `deactivate()`: always succeeds
- `uninstall()`: success, failure, already absent (match upstream semantics)

### Test patterns
```python
# Mock binary detection
monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/my-tool")

# Mock command output
runner = MockRunner(stdout="my-tool 1.0.0", returncode=0)
component = MyComponent(runner=runner)
```

## Step 5: Validate

```bash
# Lint
ruff check src/apoch/stack/components/my_tool.py tests/stack/components/test_my_tool.py

# Unit tests
PYTHONPATH=/root/Apoch-AI/src python -m pytest tests/stack/components/test_my_tool.py -v

# Full regression
PYTHONPATH=/root/Apoch-AI/src python -m pytest tests/stack/ -v
```

## Step 6: Structural Comparison

Before merging, compare your adapter against OpenSpec:

```
# Same 8 methods in same order?
grep -n "^    async def\|^    @property" src/apoch/stack/components/openspec.py
grep -n "^    async def\|^    @property" src/apoch/stack/components/my_tool.py

# Same error message patterns?
grep "not found on PATH\|installed successfully\|Installation failed" \
  src/apoch/stack/components/openspec.py src/apoch/stack/components/my_tool.py
```

Every structural difference must be **justified by a documented limitation of the upstream CLI**.

## Reference Files

- **Reference Component**: `src/apoch/stack/components/openspec.py` + `tests/stack/components/test_openspec.py`
- **Engram pattern** (platform dispatch): `src/apoch/stack/components/engram.py`
- **No-doctor pattern** (health + verify): `src/apoch/stack/components/context7.py`
- **ADR**: `openspec/changes/pr7-context7-component/adr-clicomponent-evaluation.md`
