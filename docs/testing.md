# Testing Guide

## Running the Suite

```bash
uv run pytest                     # Full suite (1,105 tests, ~6s)
uv run pytest -x                  # Stop on first failure
uv run pytest --lf                # Re-run last failures only
uv run pytest -k "codegraph"      # Filter by keyword
```

## Running Specific Tests

```bash
# Single file
uv run pytest tests/stack/components/test_codegraph.py -v

# Single class
uv run pytest tests/stack/components/test_codegraph.py::TestDetect -v

# Single method
uv run pytest tests/stack/components/test_codegraph.py::TestDetect::test_not_installed_when_binary_missing -v
```

## Test Patterns

### MockRunner for Command Mocking

All stack tests avoid real subprocess calls. Use `MockRunner` to inject fake command output:

```python
from apoch.stack.runner import MockRunner, RunResult

runner = MockRunner(result=RunResult(returncode=0, stdout="my-tool 1.0.0"))
component = MyComponent(runner=runner)
```

| Field | Purpose |
|-------|---------|
| `returncode` | Simulated exit code (0 = success) |
| `stdout` | Simulated standard output |
| `stderr` | Simulated standard error |
| `duration` | Simulated wall-clock seconds |

### monkeypatch for Binary Detection

```python
# Binary not found on PATH
monkeypatch.setattr("shutil.which", lambda name: None)

# Binary found at specific path
monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/my-tool")
```

### Custom Runner Logic for Complex Scenarios

Override `runner.run` when different commands need different outputs:

```python
async def _run(cmd, *, timeout=None, env=None):
    if "--version" in cmd:
        return RunResult(returncode=0, stdout="1.3.1\n")
    if "--help" in cmd:
        return RunResult(returncode=1, stderr="unknown option")
    return RunResult(returncode=0, stdout="")

runner.run = _run
component = MyComponent(runner=runner)
```

## Fixtures

| Fixture | Location | Purpose |
|---------|----------|---------|
| `MockRunner` | `apoch.stack.runner` | Configurable command double |
| `RunResult` | `apoch.stack.runner` | Expected command output dataclass |
| `monkeypatch` | pytest built-in | Mock `shutil.which` for binary detection |
| `conftest.py` | `tests/stack/conftest.py` | Shared session fixtures |

## Async Testing

All lifecycle methods are async. `pytest-asyncio` is configured with `asyncio_mode = "auto"` in `pyproject.toml`, so test methods can use `async def` directly:

```python
class TestDetect:
    async def test_not_installed_when_binary_missing(self, monkeypatch):
        comp = CodeGraphComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: None,
        )
        info = await comp.detect()
        assert info.installed is False
```

No `@pytest.mark.asyncio` decorator needed — auto-mode handles it.

## Coverage

```bash
uv run pytest --cov=src/apoch          # Coverage report
uv run pytest --cov=src/apoch --cov-report=html  # HTML report
```

Coverage threshold: 80% (enforced by SDD methodology).

## Ruff

```bash
uv run ruff check src/ tests/          # Lint all source and tests
uv run ruff format src/ tests/         # Format all source and tests
```

Both must pass cleanly before any PR merge.

## What to Test

Every adapter must cover:

| Area | What to verify |
|------|---------------|
| **Descriptor** | All `CODEGRAPH_DESCRIPTOR` fields (id, name, kind, version, install_command, homepage, etc.) |
| **Version parser** | Prefixed, bare, multiline, nonsense, empty |
| **Component** | Default runner, custom runner injection, descriptor property |
| **Entry point** | Resolution via `importlib.metadata.entry_points()` |
| **detect()** | Not installed, success, CLI error, unparseable version |
| **install()** | Success, failure, binary not found after install |
| **verify()** | Not installed, success, check command fails |
| **health()** | Healthy, degraded, down |
| **activate()** | Installed, not installed |
| **deactivate()** | Always succeeds |
| **uninstall()** | Success, failure, already absent |

## Test Isolation

Each test creates its own component instance with an injected `MockRunner`. No shared state between tests. No global fixtures that could leak between test runs.

```python
# Each test is fully self-contained
def test_something(self, monkeypatch):
    runner = MockRunner(stdout="1.0.0", returncode=0)
    component = MyComponent(runner=runner)
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/my-tool")
    result = await component.detect()
    assert result.installed is True
```
