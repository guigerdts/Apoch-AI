# Design: CodeGraph Stack Component

## Technical Approach

Adapter-only — no internal reimplementation. `CodeGraphComponent` mirrors the OpenSpec component's structure exactly, with three codegraph-specific variances: bare semver version regex (no prefix), verify via `--help` (Context7 no-doctor pattern), and health via `codegraph status --json` with JSON-first + exit-code fallback (OpenSpec hybrid pattern). No changes to the Core Stack (`StackComponent`, `StackManager`, `CommandRunner`).

## Architecture Decisions

| Decision | Options | Tradeoff | Chosen |
|----------|---------|----------|--------|
| Descriptor naming | `DESCRIPTOR` (OpenSpec) vs `CODEGRAPH_DESCRIPTOR` (Context7 pattern) | `DESCRIPTOR` is simpler; `CODEGRAPH_DESCRIPTOR` avoids import conflicts | `CODEGRAPH_DESCRIPTOR` — consistent with Context7 (`CONTEXT7_DESCRIPTOR`) and Engram (`ENGRA_DESCRIPTOR`) |
| Version parser naming | Public `parse_codegraph_version` (OpenSpec) vs private `_parse_version` (Context7) | Public is more testable; private avoids API surface churn | Private `_parse_version` — consistent with Context7. Bare semver is trivial to parse, no external callers expected |
| Verify strategy | `openspec doctor` → `codegraph --help` | No doctor available; `--help` confirms binary responds | `--help` (Context7 pattern). Two-phase: detect + `codegraph --help` |
| Health strategy | detect-only (Context7) vs `codegraph status --json` with fallback | `status --json` always returns exit 0 + JSON even outside projects. Richer diagnostics than detect-only | JSON-first: parse `status --json`, return full JSON as diagnostics. Fallback to exit code if unparseable |
| Install method | npm vs curl installer | curl is leaner but npm is the standard; all existing adapters use npm | npm — matches OpenSpec/Context7 exactly. Single install path for all adapter components |

## Data Flow

```
┌──────────────┐     shutil.which("codegraph")     ┌──────────────┐
│  StackManager │ ──────────────────────────────→ │  CodeGraph   │
│  (caller)     │ ←── ComponentInfo ────────────── │  Component   │
└──────────────┘                                   └──────┬───────┘
                                                           │
                                         ┌─────────────────┼─────────────────┐
                                         │                 │                 │
                                    detect()          verify()          health()
                                         │                 │                 │
                                    codegraph --     codegraph --     codegraph status
                                    version          help             --json
```

## File Changes

| File | Action | PR | Description |
|------|--------|----|-------------|
| `src/apoch/stack/components/codegraph.py` | Create | PR8.1 | CodeGraphComponent with DESCRIPTOR, `_parse_version`, `__init__`. All lifecycle methods as `NotImplementedError` stubs. |
| `src/apoch/stack/components/__init__.py` | Modify | PR8.1 | Add `CODEGRAPH_DESCRIPTOR` + `CodeGraphComponent` exports |
| `pyproject.toml` | Modify | PR8.1 | Add `codegraph` entry point to `apoch.stack.components` group |
| `tests/stack/components/test_codegraph.py` | Create | PR8.1 | Foundation tests: descriptor, parser, component instantiation, entry point, stub behavior. |
| `src/apoch/stack/components/codegraph.py` | Modify | PR8.2 | Implement lifecycle methods: detect, health (status --json), install, uninstall, verify (--help), activate, deactivate |
| `tests/stack/components/test_codegraph.py` | Modify | PR8.2 | Add lifecycle tests: detect, health, install, uninstall, verify, activate, deactivate |

## Interfaces / Contracts

### Descriptor

```python
CODEGRAPH_DESCRIPTOR = StackDescriptor(
    id="codegraph",
    name="CodeGraph",
    kind="integrations",
    version="1.4.1",
    entry_point="apoch.stack.components.codegraph:CodeGraphComponent",
    install_command="npm install -g @colbymchenry/codegraph",
    install_manager="npm",
    homepage="https://colbymchenry.github.io/codegraph/",
    repository="https://github.com/colbymchenry/codegraph",
    docs_url="https://colbymchenry.github.io/codegraph/",
    requires=("node",),
    capabilities=("code-intelligence", "knowledge-graph", "mcp"),
)
```

### Version regex (bare semver — no prefix)

```python
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)", re.MULTILINE)

def _parse_version(output: str) -> str | None:
    if match := _VERSION_RE.search(output):
        return match.group(1)
    log.warning("Could not parse CodeGraph version from output: %r", output[:200])
    return None
```

### Health response shape

```python
# success case
{"status": "healthy", "component": "codegraph", "version": "1.3.1",
 "diagnostics": {"version": "1.3.1", "initialized": False, ...}}
# not installed
{"status": "down", "component": "codegraph", "version": None}
# JSON unparseable
{"status": "healthy", "component": "codegraph", "version": "1.3.1"}  # fallback to exit code
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_parse_version` — bare semver, no prefix, edge cases | Parameterized on stdin strings (Context7 pattern). All OpenSpec format variants expected to fail. |
| Unit | Descriptor fields | Assert each field matches npm registry values (OpenSpec pattern) |
| Unit | Entry point resolution | `importlib.metadata` assertion (OpenSpec pattern) |
| Lifecycle | detect, install, uninstall, verify (--help), health (status --json), activate, deactivate | `MockRunner` + `monkeypatch` for `shutil.which` (established test pattern from OpenSpec/Context7) |
| Edge | Health JSON unparseable → exit code fallback | Mock bad stdout, verify fallback path |
| Edge | Health JSON without expected fields → exit code fallback | Mock valid JSON without version/initialized fields, verify graceful degradation |

## Threat Matrix

N/A — no routing, shell subprocess injection (CommandRunner is a shared abstraction), VCS/PR automation, executable-file classification, or process-integration boundary. All external calls go through the same `CommandRunner` interface used by every other adapter.

## Migration / Rollout

No migration required. New adapter — no existing state to migrate. Ships as part of a force-chained PR (PR8.1 Foundation + PR8.2 Core).

## Open Questions

None — all decisions resolved in proposal and verified against the official CLI documentation.
