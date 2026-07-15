# Development Guide

## Setup

```bash
git clone https://github.com/guigerdts/Apoch-AI.git
cd Apoch-AI
uv sync                   # Install all dependencies (including dev)
source .venv/bin/activate # Activate the virtual environment
```

## Running Tests

| Command | What it runs |
|---------|-------------|
| `uv run pytest` | Full suite (1,105 tests) |
| `uv run pytest tests/stack/ -v` | All stack tests |
| `uv run pytest tests/stack/components/test_codegraph.py -v` | Single test file |
| `uv run pytest tests/stack/components/test_codegraph.py::TestDetect -v` | Single test class |
| `uv run pytest tests/stack/components/test_codegraph.py::TestDetect::test_not_installed_when_binary_missing -v` | Single test method |

## Linting

```bash
uv run ruff check src/ tests/    # Lint
uv run ruff format src/ tests/   # Format
```

Ruff runs in strict mode (`select = ["E", "F", "I", "N", "W", "UP"]`). All code must pass before merging.

## Code Conventions

| Convention | Rule |
|-----------|------|
| Python | 3.13+ (uses `list \| dict` syntax, `datetime.UTC`) |
| Strings | f-strings everywhere. No `%` formatting or `.format()` |
| Async | All I/O-bound methods are `async def`. Use `asyncio` for subprocess calls |
| Exceptions | Raise `ApochError` subclasses. Never print raw tracebacks to users |
| Imports | Standard library → third-party → local, groups separated by blank line |
| Types | Full type annotations on all function signatures |
| Docstrings | Google-style for public APIs, inline for internal logic |

## Project Structure

```
src/apoch/               # Package root
├── __init__.py           # Version: 0.7.0-alpha
├── __main__.py           # python -m apoch entry
├── cli/                  # Typer CLI commands
│   ├── app.py            # Main Typer app + entry_point()
│   ├── stack.py          # apoch stack {status,install,uninstall,verify}
│   ├── doctor.py         # apoch doctor
│   ├── list.py           # apoch list
│   ├── mcp.py            # apoch mcp {start,stop,restart}
│   └── ...
├── core/                 # Event-driven engine, module lifecycle
│   ├── engine.py         # Core Engine
│   ├── events.py         # Typed event bus
│   ├── module.py         # Module ABC
│   ├── registry.py       # Module discovery and lifecycle
│   └── exceptions.py     # ApochError hierarchy
├── config/               # Layered config (defaults → YAML → env vars)
├── stack/                # Core Stack (FROZEN)
│   ├── component.py      # StackComponent ABC + ComponentInfo
│   ├── descriptor.py     # StackDescriptor frozen dataclass
│   ├── manager.py        # StackManager lifecycle orchestrator
│   ├── state.py          # StackState FSM (11 states)
│   ├── result.py         # OperationResult
│   ├── runner.py         # CommandRunner / RealRunner / MockRunner
│   ├── registry.py       # StackRegistry with entry-point discovery
│   ├── exceptions.py     # Stack-specific ApochError subclasses
│   ├── factory.py        # create_manager() factory
│   └── components/       # Adapter implementations
│       ├── openspec.py   # OpenSpec adapter (reference component)
│       ├── engram.py     # Engram adapter
│       ├── context7.py   # Context7 adapter
│       └── codegraph.py  # CodeGraph adapter
├── modules/              # Native modules
│   ├── chronicle/        # Activity recording (SQLite) — stable
│   ├── guardian/         # Exception isolation — stable
│   ├── vision/           # Observability — stable
│   ├── oracle/           # Decision analysis — implemented
│   ├── pulse/            # Performance benchmarking — implemented
│   └── optimizer/        # Context optimization — implemented
├── adapters/             # Agent adapter layer
│   ├── base.py           # AgentAdapter ABC
│   ├── manager.py        # AgentAdapterManager orchestrator
│   ├── registry.py       # Adapter registry with plugin loading
│   └── opencode/         # OpenCode adapter (FastMCP gateway)

tests/                    # Mirrors src/apoch/ structure
├── stack/                # Stack tests (~361 test functions)
│   ├── components/       # Per-adapter test files
│   ├── conftest.py       # Shared fixtures
│   └── test_*.py         # Core Stack tests
├── modules/              # Module tests
└── test_*.py             # CLI, engine, events, adapters tests

docs/                     # Project documentation
openspec/                 # SDD artifacts (specs, designs, changes)
```

## Dependencies

Managed in `pyproject.toml` via `uv`. Runtime and dev dependencies are isolated:

```bash
uv add <package>          # Add a runtime dependency
uv add --dev <package>    # Add a dev dependency
uv sync                   # Sync lockfile
```

## Building

```bash
uv build                  # Build sdist + wheel in dist/
```

## CLI Reference

```bash
apoch stack status          # Show component states
apoch stack install [...]   # Install components
apoch stack uninstall [...] # Uninstall components
apoch stack verify [...]    # Verify installations
apoch doctor                # System diagnostics
apoch list                  # Available components
apoch mcp start|stop|restart # MCP gateway lifecycle
```
