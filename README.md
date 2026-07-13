# Apoch-AI

Enhancement framework for AI coding agents.
Augments OpenCode and other agents with intelligent modules:
memory, context management, code intelligence, observability, integrations.
Stack: Python. Cross-platform. Developer-first.
**Estado:** v0.5.0-alpha — Core + 3 módulos implementados (Chronicle, Guardian, Vision).


# Apoch-AI

## Project Master Document
Version: 0.1
Status: Approved
Development Methodology: OpenSpec (Spec-Driven Development)

---

# 1. Project Overview

Apoch-AI is an enhancement framework for AI coding agents.

Its purpose is NOT to replace coding agents such as OpenCode, Claude Code, Codex, Gemini CLI, Kiwi, Aider or future agents.

Its purpose is to enhance their capabilities by providing an extensible platform that installs additional components, integrations and intelligent modules.

Apoch-AI must behave as a native extension of the supported agent.

It must never require users to change their workflow.

---

# 2. Vision

Create the best enhancement framework for AI coding agents.

The framework must install, configure and maintain a complete professional development environment over an existing agent.

Long-term support for multiple agents.

Version 1 only targets OpenCode.

The architecture MUST remain agent agnostic.

---

# 3. Philosophy

Never reinvent features that already exist inside the target agent.

Instead:

- Enhance
- Integrate
- Extend
- Observe
- Improve

Every feature implemented by Apoch-AI must provide value that the agent does not already provide.

---

# 4. Primary Goals

- Simple installation.
- Native integration.
- Zero workflow disruption.
- Modular architecture.
- Cross-platform compatibility.
- Professional developer experience.
- Community extensibility.

---

# 5. Out of Scope

Apoch-AI is NOT:

- a coding agent
- an LLM
- a model provider
- an IDE
- a dashboard application
- a replacement for OpenCode

---

# 6. Initial Target

Supported Agent:

OpenCode

Future support:

- Claude Code
- Codex
- Gemini CLI
- Kiwi
- Aider
- Additional agents

Future support must not influence Version 1 implementation.

---

# 7. Installation Experience

The installation experience should resemble Gentle-AI.

The user installs Apoch-AI once.

After installation, Apoch-AI integrates with the selected agent.

The user continues using the agent normally.

No wrappers.

No forks.

No modified workflows.

---

# 8. Core Stack

Apoch-AI installs and manages the following core integrations.

- OpenSpec
- Engram
- Context7
- CodeGraph

These are considered part of the platform.

---

# 9. Core Modules

Apoch-AI introduces the following native modules.

Status: ✅ Implemented — 🔄 In progress — ⏳ Pending

Chronicle ✅ `v0.3.0-alpha`

Activity recording and timeline generation. SQLite-based event store with WAL,
auto-prune, and dynamic filter queries. Implements spec subset: event recording,
persistent storage, query interface, retention/pruning.

Oracle ⏳

Decision analysis and reasoning.

Guardian ✅ `v0.4.0-alpha`

Exception isolation and execution boundaries. Wraps module lifecycle calls
with structured diagnostics capture. Implements spec subset: exception boundaries,
state tracking, post-failure diagnostics, graceful degradation. Timeouts and
policy enforcement deferred to future releases.

Vision ✅ `v0.6.0-alpha`

Full observability suite: structured NDJSON logging with rotation, ring buffer, module
state/config introspection, system info (PID, memory, platform), degraded mode support,
and optional Chronicle integration via duck-typed services.

Pulse ⏳

Performance benchmarking.

Optimizer ⏳

Context and token optimization.

---

# 10. Roadmap

Development follows the approved roadmap. Current progress:

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Foundation (project setup, uv, CI, testing) | ✅ Complete |
| Phase 1 | Core (Engine, Module, Registry, Events, Config, Exceptions) | ✅ Complete — `v0.1.0` |
| Phase 2 | OpenCode Integration (Adapter, CLI, opencode.json manager) | ✅ Complete — `v0.2.0-alpha` |
| Phase 3 | Core Modules | 🔄 In progress |
| | — PR3A: Chronicle Foundation | ✅ `v0.3.0-alpha` |
| | — PR3B: Guardian Module | ✅ `v0.4.0-alpha` |
| | — PR3C-A: Vision Foundation | ✅ `v0.5.0-alpha` |
| | — PR3C-B: Vision Query APIs | ✅ `v0.6.0-alpha` |
| | — Pulse, Optimizer, Oracle | ⏳ Pending |
| Phase 4 | Ecosystem | ⏳ Pending |
| Phase 5 | Stabilization | ⏳ Pending |

The roadmap is considered frozen.

Any modification requires explicit approval.

---

# 11. Project Rules

Rule 001

Never modify OpenCode source code.

Rule 002

Never fork OpenCode.

Rule 003

Use official APIs whenever possible.

Rule 004

Everything must be modular.

Rule 005

Core must never depend on modules.

Rule 006

Modules must be installable independently.

Rule 007

Integrations must be reversible.

Rule 008

Support:

- Windows
- macOS
- Linux
- WSL
- Termux

Rule 009

Every new feature requires approval.

Rule 010

Never duplicate functionality already provided by OpenCode.

---

# 12. Development Methodology

The project follows Spec-Driven Development using OpenSpec.

Implementation without an approved specification is forbidden.

Every feature must follow:

Proposal

↓

Specification

↓

Tasks

↓

Implementation

↓

Validation

---

# 13. Technology Decisions

Language:

Python

Project Management:

uv

Architecture:

Modular

Interface:

CLI / TUI

Package Distribution:

Python package

Target:

Cross-platform

---

# 14. Repository Principles

The repository must remain:

- clean
- modular
- documented
- scalable
- production-ready

No experimental code should enter the main branch.

---

# 15. Success Criteria

Version 1 is considered complete when:

- Core framework is operational.
- OpenCode integration is stable.
- Core Stack installs correctly.
- All six core modules are functional.
- Installation is simple.
- Documentation is complete.
- Tests pass.
- Cross-platform compatibility is verified.

---

# 16. Instructions for OpenCode

You are expected to act as the lead software architect.

Do not make architectural assumptions.

Do not introduce additional features without approval.

Challenge design decisions if they violate the project principles.

Always follow OpenSpec.

Always prioritize maintainability, modularity and long-term extensibility over short-term convenience.
