# Installation Guide

**Apoch-AI** v0.7.0-alpha — Python 3.13+, managed with [uv](https://docs.astral.sh/uv/).

---

## Minimum Requirements

| Requirement | Version | Why |
|-------------|---------|-----|
| **Python** | >= 3.13 | Runtime |
| **git** | any | Clone the repo |
| **uv** | latest | Dependency management (see install path below) |
| **Node.js + npm** | >= 20.19.0 | Required by some stack components (OpenSpec, CodeGraph, Context7) |

> **Only Python, git, and uv are needed to run Apoch-AI itself.**  
> Node.js and npm are only needed if you install third-party stack components on top.

---

## Prerequisites (by platform)

### Linux / macOS

| Tool | Install command |
|------|----------------|
| **uv** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js** | `apt install nodejs npm` (Debian/Ubuntu) or `brew install node` (macOS) |

### Termux (Android)

The `uv` install script doesn't support `aarch64-linux-android`, so use `pip` directly:

```bash
pkg update && pkg upgrade
pkg install python git nodejs
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Every `uv run apoch ...` command must be prefixed with `uv run` on Linux/macOS.  
On Termux, use `.venv/bin/apoch ...` instead (or activate the venv first).

---

## Install from Source (Linux / macOS)

```bash
# 1. Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the repo
git clone https://github.com/guigerdts/Apoch-AI.git
cd Apoch-AI

# 3. Sync dependencies
uv sync
```

This creates a virtual environment at `.venv/` and installs all dependencies.

## Install from Source (Termux)

```bash
pkg update && pkg upgrade
pkg install python git nodejs
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

> On Termux, activate the venv first (`source .venv/bin/activate`) or use `.venv/bin/apoch` instead of `uv run apoch`.

## Install from PyPI — ⚠️ Not Yet Available

> **Apoch-AI has NOT been published to PyPI yet.**  
> The only installation method is [from source](#install-from-source).  
> This section documents the future intent — skip it for now.

```bash
pip install apoch-ai        # ⛔ won't work until published
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

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Linux (x86_64) | ✅ Supported | Primary target |
| macOS (arm64 / x86_64) | ✅ Supported | Tested on Apple Silicon |
| Windows (WSL) | ✅ Supported | Use the Linux instructions inside WSL |
| Termux (aarch64) | ⚠️ Works | Uses pip instead of uv, see [Termux install](#install-from-source-termux) above |
