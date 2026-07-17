# FAQ — Frequently Asked Questions

## General

### What is Apoch-AI?

Apoch-AI is an enhancement framework for AI coding agents. It augments agents like OpenCode with persistent capabilities they cannot maintain across sessions: project memory, engineering governance, runtime observability, and toolchain integration. It is **not** a coding agent — it is a platform that enhances existing agents.

### Do I need to change my workflow?

No. Apoch-AI integrates with your existing agent. It does not wrap, fork, or modify your workflow. After installation, you continue using your agent normally.

### Which agents are supported?

Version 1 targets **OpenCode**. The architecture is agent-agnostic and designed for future support of Claude Code, Codex, Gemini CLI, Kiwi, Aider, and others.

### Is Apoch-AI an IDE?

No. Apoch-AI is a CLI framework and Python package. It has no graphical interface.

---

## Installation

### How do I install Apoch-AI?

> **Apoch-AI has NOT been published to PyPI yet.**  
> Use the source installation below.

```bash
# ✅ This works now:
curl -LsSf https://astral.sh/uv/install.sh | sh    # install uv first
git clone https://github.com/guigerdts/Apoch-AI.git
cd Apoch-AI
uv sync

# ⛔ This won't work yet:
# pip install apoch-ai
```

### What are the prerequisites?

- Python 3.13 or later
- [uv](https://docs.astral.sh/uv/) (package manager)
- Node.js (for npm-based components: OpenSpec, Context7, CodeGraph)
- Homebrew (optional, for Engram on macOS)

### How do I install stack components?

```bash
apoch stack install           # install all registered components
apoch stack install openspec  # install a single component
```

---

## Components

### What components are available?

Four adapters are implemented:

| Component | Purpose | Install Method |
|-----------|---------|---------------|
| OpenSpec | Spec-Driven Development | `npm install -g @fission-ai/openspec@latest` |
| Engram | Persistent memory | `brew install gentleman-programming/tap/engram` |
| Context7 | Doc intelligence | `npm install -g ctx7` |
| CodeGraph | Code knowledge graph | `npm install -g @colbymchenry/codegraph` |

### Can I use Apoch-AI without installing all components?

Yes. Each component is independent. Run `apoch stack install <name>` to install only what you need.

### Why does OpenSpec not appear in `apoch stack status`?

Ensure the package entry point is registered. Run:

```bash
uv run python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='apoch.stack.components')])"
```

If `openspec` is not listed, reinstall Apoch-AI or check `pyproject.toml`.

---

## Troubleshooting

### `apoch stack status` shows all components as NOT_INSTALLED

This means the CLI tools are not on your PATH. Install each tool globally (see per-component install commands above) or ensure their directories are in `$PATH`.

### `npm install -g` fails with permission errors

On Unix systems, global npm installs may require `sudo` or a configured npm prefix:

```bash
# Option 1
sudo npm install -g <package>

# Option 2 (recommended)
npm config set prefix ~/.npm
export PATH="$HOME/.npm/bin:$PATH"
```

### How do I run tests?

```bash
uv run pytest                           # full suite
uv run pytest tests/stack/components/   # component tests only
uv run pytest tests/stack/components/test_codegraph.py -v  # single file
```

### Ruff is reporting lint errors. How do I fix them?

```bash
ruff check src/ tests/       # check all files
ruff check --fix src/ tests/ # auto-fix where possible
ruff format src/ tests/      # format
```

---

## Development

### How do I add a new component adapter?

See [Creating a New Adapter](creating-a-new-adapter.md) for the complete step-by-step guide. The short version:

1. Copy `src/apoch/stack/components/openspec.py` as template
2. Change tool-specific fields (DESCRIPTOR, binary name, commands)
3. Register in `pyproject.toml` under `apoch.stack.components`
4. Write tests using MockRunner + monkeypatch

### Can I modify the Core Stack?

**No.** The Core Stack (`StackComponent`, `StackManager`, `ComponentInfo`, `ComponentStatus`, `StackState`, `derive_state()`, CLI, `descriptor.py`) is **frozen**. No modifications are allowed.

### What is the Reference Component Rule?

OpenSpec (`src/apoch/stack/components/openspec.py`) is the reference component. Every new adapter must follow its structure exactly. Any structural difference must be justified by a documented limitation of the upstream CLI.

---

## Architecture

### What is the difference between ERROR and BROKEN states?

- **ERROR**: The component entered an invalid state during an operation (install failed, detect raised an exception). Retry the operation.
- **BROKEN**: The component is installed but verification failed (e.g., `--help` returned non-zero). Reinstall or fix the installation.

See [Core Stack Reference](core-stack.md#state-machine--valid-transitions) for the full state transition table.

### Why does health() have different strategies per adapter?

Each upstream CLI exposes different diagnostics:

| Adapter | Health Strategy |
|---------|----------------|
| OpenSpec | `openspec doctor --json` → parse `root.healthy` |
| Engram | detect-only (binary + version) |
| Context7 | detect-only (binary + version) |
| CodeGraph | `codegraph status --json` → always returns valid JSON |

This is by design — adapters match the capabilities of the upstream tool.

---

## SDD Methodology

### What is Spec-Driven Development?

SDD is the development methodology used by Apoch-AI. Every feature follows this flow:

```
Proposal → Spec → Design → Tasks → Apply → Verify → Archive
```

Implementation without an approved specification is forbidden. See [OpenSpec](https://openspec.dev/) for details.

### How are PRs structured?

Large changes use **chained PRs** (stacked-to-main):

- PR8.1: Foundation (skeleton, exports, entry point)
- PR8.2: Core Lifecycle (full implementation)

Each PR is independently reviewable, under 400 changed lines, and merges to main.

---

## MCP Public API

### What MCP tools does Apoch-AI expose?

Seven public tools:

| Tool | What it tells you |
|------|-------------------|
| `apoch_status` | Is the system healthy? What components are active? Any recent activity? |
| `apoch_health` | Are there active problems? How severe? What should I do? |
| `apoch_history` | What happened recently? Tool calls, errors, lifecycle events? |
| `apoch_recommend` | What should I do next to improve the project? |
| `apoch_progress` | How much work happened today/this week/this month? |
| `apoch_insights` | Are there patterns or anomalies in my development workflow? |
| `apoch_logs` | What do the raw debug logs say? Any errors or warnings? |

Plus 5 legacy aliases for backward compatibility (see [migration guide](mcp-public-api.md#migration-guide)).

### How do I call these tools from an AI agent?

The tools are served over MCP stdio transport. When you run `uv run apoch mcp serve`, the gateway registers all tools. An agent like OpenCode can then discover and invoke them through its MCP client.

### Is there a REST API?

No. The API uses the Model Context Protocol over stdio transport. This is the standard protocol for AI coding agents.

### What does a tool response look like?

Every successful response has these fields:

```json
{
  "api_version": "1.0",
  "summary": "🟢 Todos los sistemas operativos",
  "explanation": "Todos los módulos respondieron correctamente.",
  "evidence": [
    {"source": "Vision", "confidence": 0.8,
     "collected_ago": 0, "based_on": "module response"}
  ],
  "suggested_action": null,
  "confidence": 1.0,
  "generated_at": "2026-07-17T12:00:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```

Error responses use a different format: `{"ok": false, "error": {"code": "ERR_...", "message": "..."}}`.

### How is confidence calculated?

Each tool computes confidence differently:

| Tool | With full data | With partial data | Without data |
|------|---------------|-------------------|-------------|
| `apoch_status` | 1.0 | 0.67 | ERR_TIMEOUT |
| `apoch_health` | 1.0 | 0.5 | ERR_DEPENDENCY_UNAVAILABLE |
| `apoch_history` | 0.50 | — | 0.30 |
| `apoch_recommend` | 0.85 | 1.0 (fallback) | ERR_TIMEOUT |
| `apoch_progress` | ≥0.7 | — | 0.3 |
| `apoch_insights` | computed | 0.56–0.42 | 0.0 |
| `apoch_logs` | 1.0 | — | 0.3 |

### What error codes can tools return?

| Code | Meaning |
|------|---------|
| `ERR_TIMEOUT` | Module didn't respond in time |
| `ERR_DEPENDENCY_UNAVAILABLE` | Required module not loaded/failed |
| `ERR_INVALID_ARGUMENT` | Bad parameter value |
| `ERR_INTERNAL` | Unexpected internal error |
| `ERR_NOT_IMPLEMENTED` | Tool not implemented yet |

See the [Error Catalog](mcp-public-api.md#error-catalog) for complete details.

### How do I migrate from old tools (vision_state, chronicle_query, etc.)?

See the [Migration Guide](mcp-public-api.md#migration-guide) for before/after examples.
