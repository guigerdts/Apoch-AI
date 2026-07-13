# Apoch-AI Coding Standards

## General
- Follow Spec-Driven Development (SDD) using OpenSpec.
- Ensure all code changes are modular and agent-agnostic.
- Write unit/integration tests for every new behavior.

## Python Code Style
- Target Python 3.13+.
- Use uv for project management.
- Strictly adhere to Ruff linting and formatting rules.
- Maintain clean, descriptive docstrings for all modules, classes, and functions.
- Handle exceptions cleanly using ApochError subclasses and avoid printing raw tracebacks to the user.
