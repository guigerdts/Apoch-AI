# Quick Start

Get Apoch-AI up and running in five minutes.

---

## 1. Install

```bash
git clone https://github.com/guigerdts/Apoch-AI.git
cd Apoch-AI
uv sync
```

Verify the CLI works:

```
$ uv run apoch --version
0.7.0-alpha
```

## 2. Check Component Status

See which stack components are installed on your system:

```
$ uv run apoch stack status

CodeGraph (integrations)
  State:       NOT_INSTALLED
  Version:     —
  Project:     https://colbymchenry.github.io/codegraph/
  Repository:  https://github.com/colbymchenry/codegraph
  Docs:        https://colbymchenry.github.io/codegraph/
  Install:     npm install -g @colbymchenry/codegraph

Context7 (integrations)
  State:       NOT_INSTALLED
  Version:     —
  Project:     https://context7.com
  Repository:  https://github.com/upstash/context7
  Docs:        https://context7.com/docs
  Install:     npm install -g ctx7

Engram (integrations)
  State:       NOT_INSTALLED
  Version:     —
  Project:     https://github.com/Gentleman-Programming/engram
  Repository:  https://github.com/Gentleman-Programming/engram
  Docs:        https://github.com/Gentleman-Programming/engram/blob/main/DOCS.md
  Install:     brew install gentleman-programming/tap/engram

OpenSpec (integrations)
  State:       NOT_INSTALLED
  Version:     —
  Project:     https://openspec.dev/
  Repository:  https://github.com/fission-ai/OpenSpec
  Docs:        https://openspec.dev/docs/
  Install:     npm install -g @fission-ai/openspec@latest
```

All four show `NOT_INSTALLED` — none are found on your system yet.

## 3. Install All Components

```bash
$ uv run apoch stack install
  ✓ codegraph: CodeGraph 1.3.1 installed
  ✓ context7: Context7 0.5.4 installed
  ✓ engram: Engram 1.19.0 installed
  ✓ openspec: OpenSpec 1.6.0 installed
```

If a component is already installed, it is skipped (idempotent).

## 4. Verify Installations

```bash
$ uv run apoch stack verify
  ✓ codegraph: CodeGraph 1.3.1 verified
  ✓ context7: Context7 0.5.4 verified
  ✓ engram: Engram 1.19.0 verified
  ✓ openspec: OpenSpec 1.6.0 verified
```

Each component runs its own diagnostic: OpenSpec and Engram use `doctor`, Context7 and CodeGraph use `--help` as a responsiveness check.

## 5. Full Health Check

```bash
$ uv run apoch stack status

CodeGraph (integrations)
  State:       INSTALLED
  Version:     1.3.1
  Project:     https://colbymchenry.github.io/codegraph/
  Repository:  https://github.com/colbymchenry/codegraph
  Docs:        https://colbymchenry.github.io/codegraph/

Context7 (integrations)
  State:       INSTALLED
  Version:     0.5.4
  Project:     https://context7.com
  Repository:  https://github.com/upstash/context7
  Docs:        https://context7.com/docs

Engram (integrations)
  State:       INSTALLED
  Version:     1.19.0
  Project:     https://github.com/Gentleman-Programming/engram
  Repository:  https://github.com/Gentleman-Programming/engram
  Docs:        https://github.com/Gentleman-Programming/engram/blob/main/DOCS.md

OpenSpec (integrations)
  State:       INSTALLED
  Version:     1.6.0
  Project:     https://openspec.dev/
  Repository:  https://github.com/fission-ai/OpenSpec
  Docs:        https://openspec.dev/docs/
```

All four show `INSTALLED` — ready to use.

## Next Steps

- [CLI Reference](./cli.md) — full command reference
- [Configuration Guide](./configuration.md) — customize Apoch-AI
- [Troubleshooting](./troubleshooting.md) — common issues and fixes
