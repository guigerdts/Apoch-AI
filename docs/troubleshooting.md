# Troubleshooting

Common issues and how to resolve them.

---

## Component Shows NOT_INSTALLED After Install

**Symptom:** `apoch stack status` shows `NOT_INSTALLED` for a component you just installed.

**Cause:** The component binary is not on `$PATH` or the version check failed.

**Check:** Run the version command manually:

| Component | Command |
|-----------|---------|
| OpenSpec | `openspec --version` |
| Engram | `engram version` |
| Context7 | `ctx7 --version` |
| CodeGraph | `codegraph --version` |

**Fix:** Ensure npm/brew global binaries are on PATH:

```bash
# npm global bin directory
npm bin -g
# → /usr/local/bin  or  /opt/homebrew/bin

# Add to PATH (if missing)
export PATH="$(npm bin -g):$PATH"
```

---

## npm Permission Errors During Install

**Symptom:** `apoch stack install openspec` fails with EACCES.

**Cause:** npm lacks write permission to its global directory.

**Fix (avoid sudo):**

```bash
# Reconfigure npm prefix to a user-owned directory
npm config set prefix ~/.npm-global
export PATH="$HOME/.npm-global/bin:$PATH"
```

Or use a Node version manager (nvm, fnm) that manages permissions automatically.

---

## Version Parse Failure

**Symptom:** A component is detected but shown as `NOT_INSTALLED` despite the binary being present.

**Cause:** `_parse_version()` returned `None` because the CLI version output did not match the expected regex.

Check the regex patterns in each component:

| Component | File | Regex |
|-----------|------|-------|
| OpenSpec | `src/apoch/stack/components/openspec.py:46` | `(?:openspec\s+)?v?(\d+\.\d+\.\d+)` |
| Engram | `src/apoch/stack/components/engram.py:48` | `(?:engram\s+)?v?(\d+\.\d+\.\d+)` |
| Context7 | `src/apoch/stack/components/context7.py:45` | `(?:ctx7\s+)?v?(\d+\.\d+\.\d+)` |
| CodeGraph | `src/apoch/stack/components/codegraph.py:47` | `(\d+\.\d+\.\d+)` |

**Diagnose:** Run the version command and compare its output against the regex.

---

## Health Check Shows Degraded

**Symptom:** A component installs successfully but `apoch stack verify` or the component's health check reports degraded.

**Diagnose:** Run the component's diagnostic directly:

```bash
openspec doctor          # OpenSpec
engram doctor            # Engram
ctx7 --help              # Context7 (basic responsiveness)
codegraph --help         # CodeGraph (basic responsiveness)
```

Engram and OpenSpec have dedicated `doctor` commands. Context7 and CodeGraph use `--help` exit code as a proxy — a non-zero exit from `--help` means the binary is broken.

---

## Component Not Registered (StackNotFoundError)

**Symptom:** `StackNotFoundError: Stack component 'X' is not registered`

**Cause:** The component name is misspelled or its entry point is missing from `pyproject.toml`.

**Fix:** List registered components and verify the name:

```bash
uv run apoch stack status
# Shows all registered components
```

Check that the entry point exists in `pyproject.toml` under `[project.entry-points."apoch.stack.components"]`. After adding an entry point, run `uv sync` to reinstall.

---

## Dependency Not Installed

**Symptom:** `Dependency 'X' is not installed` when running `apoch stack install`.

**Cause:** A component lists `X` as a dependency in its `StackDescriptor.dependencies` tuple. The dependency must be installed first.

**Fix:** Install the dependency first, then retry:

```bash
uv run apoch stack install <dependency>
uv run apoch stack install <original-component>
```

---

## brew Not Available (Engram on Windows)

**Symptom:** Engram install fails on Windows — `brew` is not available.

**Fix:** Engram detects Windows and uses `go install` instead:

```bash
go install github.com/Gentleman-Programming/engram/cmd/engram@latest
```

If Go is not installed, download the prebuilt binary from the [Engram releases page](https://github.com/Gentleman-Programming/engram/releases).

---

## Ruff Lint Errors

**Symptom:** Code fails linting checks.

**Fix:** Run Ruff to see all issues:

```bash
ruff check
ruff format
```

The project uses Ruff with select rules: `E`, `F`, `I`, `N`, `W`, `UP` (see `pyproject.toml`).

---

## Tests Fail

**Symptom:** `uv run pytest` reports failures.

**Run with verbose output:**

```bash
uv run pytest -v
```

Run a specific test file:

```bash
uv run pytest tests/stack/ -v
```

---
