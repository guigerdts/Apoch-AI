# Adapter Reference

Four adapters implement the `StackComponent` interface. Each wraps a third-party CLI tool and follows the OpenSpec Reference Component pattern. Source files are in `src/apoch/stack/components/`.

---

## OpenSpec

Adapter for the [OpenSpec](https://openspec.dev/) CLI — Spec-Driven Development for AI assistants.

| Attribute | Value |
|-----------|-------|
| **Registry ID** | `openspec` |
| **Binary** | `openspec` |
| **Package** | `@fission-ai/openspec` (npm) |
| **Install** | `npm install -g @fission-ai/openspec@latest` |
| **Uninstall** | `npm uninstall -g @fission-ai/openspec` |
| **Version** | `openspec --version` → `openspec 1.6.0` (prefixed) |
| **Doctor** | ✅ `openspec doctor` available |
| **Health** | `openspec doctor --json` → structured JSON with `root.healthy` |
| **Prerequisites** | Node.js >= 20.19.0 |
| **Tests** | 41 |
| **Source** | `src/apoch/stack/components/openspec.py` |
| **Tests file** | `tests/stack/components/test_openspec.py` |

OpenSpec is the **reference component** — all other adapters mirror its structure. It runs `openspec doctor` for verify and `openspec doctor --json` for health, with JSON-first fallback to exit code.

**Uninstall semantics**: npm — returns success when already absent (idempotent).

---

## Engram

Adapter for the [Engram](https://github.com/Gentleman-Programming/engram) CLI — persistent memory for AI coding agents.

| Attribute | Value |
|-----------|-------|
| **Registry ID** | `engram` |
| **Binary** | `engram` |
| **Package** | `github.com/Gentleman-Programming/engram` (Go) |
| **Install** | Platform-dispatch: `brew install gentleman-programming/tap/engram` (macOS/Linux), `go install github.com/...` (Windows) |
| **Uninstall** | Platform-dispatch: `brew uninstall engram` (Homebrew), `go clean -i ...` (Windows) |
| **Version** | `engram version` → with prefix (e.g. `engram 1.19.0`) |
| **Doctor** | ✅ `engram doctor` available |
| **Health** | Exit-code based via `engram doctor` |
| **Prerequisites** | None (static Go binary) |
| **Tests** | 48 |
| **Source** | `src/apoch/stack/components/engram.py` |
| **Tests file** | `tests/stack/components/test_engram.py` |

Engram uses platform-dispatch helpers for install and uninstall. It inspects `executable_path` to detect Homebrew-managed installs — only then will uninstall proceed. Manual binary installs return failure with a removal suggestion.

**Uninstall semantics**: brew — returns **failure** when already absent (`success=False`). This matches Homebrew's behavior.

---

## Context7

Adapter for the [Context7](https://context7.com/) CLI — documentation intelligence for AI coding agents.

| Attribute | Value |
|-----------|-------|
| **Registry ID** | `context7` |
| **Binary** | `ctx7` |
| **Package** | `ctx7` (npm) |
| **Install** | `npm install -g ctx7` |
| **Uninstall** | `npm uninstall -g ctx7` |
| **Version** | `ctx7 --version` → `ctx7 0.5.4` (prefixed) |
| **Doctor** | ❌ No doctor command |
| **Health** | Detect-only — binary presence + version parse |
| **Prerequisites** | Node.js >= 18 |
| **Tests** | 36 |
| **Source** | `src/apoch/stack/components/context7.py` |
| **Tests file** | `tests/stack/components/test_context7.py` |

Context7 has no `doctor` command. Verify uses `ctx7 --help` as a basic responsiveness check. Health checks only whether the binary exists and the version is parseable — no structured diagnostic output.

**Uninstall semantics**: npm — returns success when already absent (idempotent).

---

## CodeGraph

Adapter for the [CodeGraph](https://colbymchenry.github.io/codegraph/) CLI — code intelligence knowledge graph for AI coding agents.

| Attribute | Value |
|-----------|-------|
| **Registry ID** | `codegraph` |
| **Binary** | `codegraph` |
| **Package** | `@colbymchenry/codegraph` (npm) |
| **Install** | `npm install -g @colbymchenry/codegraph` |
| **Uninstall** | `npm uninstall -g @colbymchenry/codegraph` |
| **Version** | `codegraph --version` → bare semver (e.g. `1.3.1`, **no** prefix) |
| **Doctor** | ❌ No doctor command |
| **Health** | `codegraph status --json` → always returns exit 0 + valid JSON |
| **Prerequisites** | Node.js (any) — bundles own runtime |
| **Tests** | 31 |
| **Source** | `src/apoch/stack/components/codegraph.py` |
| **Tests file** | `tests/stack/components/test_codegraph.py` |

CodeGraph has no `doctor` command. Verify uses `codegraph --help` as a basic check. Health runs `codegraph status --json` — the CLI always returns exit 0 with valid JSON, so health parses it directly with no exit-code fallback path needed for the JSON case.

**Uninstall semantics**: npm — returns success when already absent (idempotent).

---

## Comparison

| Attribute | OpenSpec | Engram | Context7 | CodeGraph |
|-----------|----------|--------|----------|-----------|
| **Binary** | `openspec` | `engram` | `ctx7` | `codegraph` |
| **Install method** | npm | brew / go install | npm | npm |
| **Version format** | Prefixed | Prefixed | Prefixed | Bare semver |
| **Version command** | `--version` | `version` | `--version` | `--version` |
| **Doctor** | ✅ `doctor` | ✅ `doctor` | ❌ `--help` | ❌ `--help` |
| **Health strategy** | JSON via `doctor --json` | Exit code via `doctor` | Detect-only | JSON via `status --json` |
| **Uninstall semantics** | Idempotent (npm) | Fail on absent (brew) | Idempotent (npm) | Idempotent (npm) |
| **Prerequisites** | Node.js >= 20.19.0 | None | Node.js >= 18 | Node.js (any) |
| **Package manager** | npm | Homebrew / go | npm | npm |
| **Tests** | 41 | 48 | 36 | 31 |

---

## Lifecycle Pattern

All four adapters follow the same universal lifecycle:

```
detect() ──→ install() ──→ uninstall() ──→ verify() ──→ activate() ──→ deactivate() ──→ health()
```

### Detection (common scaffold)

```python
async def detect(self) -> ComponentInfo:
    binary = shutil.which("<name>")          # 1. Find binary on PATH
    if binary is None:
        return ComponentInfo(installed=False)
    result = await self._runner.run(["<name>", "--version"])  # 2. Run version check
    version = _parse_version(result.stdout)   # 3. Parse version string
    return ComponentInfo(
        installed=True, version=version, executable_path=Path(binary),
    )
```

### Test Patterns

All 401 stack tests use the same infrastructure:

- **`MockRunner`** — inject a fake `CommandRunner` that returns a configurable `RunResult`:
  ```python
  runner = MockRunner(result=RunResult(returncode=0, stdout="my-tool 1.0.0"))
  component = MyComponent(runner=runner)
  ```
- **`monkeypatch`** — mock `shutil.which` for binary-not-found scenarios:
  ```python
  monkeypatch.setattr("shutil.which", lambda name: None)
  ```

### Health Strategies

The four adapters cover three health strategies:

| Strategy | Adapters | Approach |
|----------|----------|----------|
| **Structured JSON** | OpenSpec, CodeGraph | Run a `--json` subcommand and parse the output |
| **Exit-code** | Engram | Run `doctor`, check return code |
| **Detect-only** | Context7 | No subcommand — binary presence + version parse |

### Variance Points

Cross-cutting differences when implementing a new adapter:

| Scenario | Pattern | Examples |
|----------|---------|----------|
| No universal install command | `platform.system()` dispatch | Engram (brew vs go install) |
| No doctor command | `--help` for verify, detect-only for health | Context7, CodeGraph |
| Different uninstall semantics | Match the upstream's behavior | Engram (brew: fail on absent) vs npm (idempotent) |
| Rich health JSON | JSON parse with fallback | OpenSpec (`doctor --json`), CodeGraph (`status --json`) |
| Binary path analysis | Inspect `executable_path` for install method | Engram (Homebrew vs manual detection) |

For the step-by-step guide to creating a new adapter, see [creating-a-new-adapter.md](creating-a-new-adapter.md).
