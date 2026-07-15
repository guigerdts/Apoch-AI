# Installation Guide

**Apoch-AI** v0.7.0-alpha — Python 3.13+, managed with [uv](https://docs.astral.sh/uv/).

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | >= 3.13 | `python --version` |
| uv | latest | `uv --version` |
| Node.js | >= 20.19.0 | `node --version` (for OpenSpec, CodeGraph) |
| npm | bundled with Node | `npm --version` |
| Homebrew | latest | `brew --version` (macOS/Linux, for Engram) |

## Install from Source (Current)

```bash
git clone https://github.com/guigerdts/Apoch-AI.git
cd Apoch-AI
uv sync
```

This creates a virtual environment at `.venv/` and installs all dependencies.

## Install from PyPI — ⚠️ Not Yet Available

> **Apoch-AI has NOT been published to PyPI yet.**  
> The only installation method is [from source](#install-from-source).  
> This section documents the future intent — skip it for now.

```bash
pip install apoch-ai        # ⛔ won't work until published
uv pip install apoch-ai     # ⛔ won't work until published
```

## Verify Installation

```bash
uv run apoch --version
# → 0.7.0-alpha
```

Or if installed globally:

```bash
apoch --version
```

## Install Stack Components

Apoch manages four third-party CLI tools as *stack components*:

| Component | Install Command | Manager |
|-----------|----------------|---------|
| OpenSpec | `npm install -g @fission-ai/openspec@latest` | npm |
| Engram | `brew install gentleman-programming/tap/engram` | Homebrew |
| Context7 | `npm install -g ctx7` | npm |
| CodeGraph | `npm install -g @colbymchenry/codegraph` | npm |

Install all at once:

```bash
uv run apoch stack install
```

Install individually:

```bash
uv run apoch stack install openspec
uv run apoch stack install engram
```

## Troubleshooting PATH

If `uv run apoch` works but `apoch` does not, add the Python binary directory to your `$PATH`:

```bash
# macOS/Linux (with venv)
export PATH="$PWD/.venv/bin:$PATH"

# Or globally (varies by system)
export PATH="$HOME/.local/bin:$PATH"
```

**npm global binaries** must also be on PATH. Locate them with:

```bash
npm bin -g
# → /usr/local/bin  (or /opt/homebrew/bin on Apple Silicon)
```
