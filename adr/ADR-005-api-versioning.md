# ADR-005 — API Versioning

**Date:** 2026-07-14
**Status:** Approved
**Context:** The MCP Public API returns a version field in every response (`api_version`). Clients use this to detect breaking changes, deprecations, or new capabilities. The versioning scheme must be simple, predictable, and independent of the project's own version.

---

## 1. Objective

### 1.1 What this ADR guarantees

- Every `ToolResponse` includes `api_version: "MAJOR.MINOR"` as its first field.
- **MAJOR**: breaking changes (removing or renaming required fields).
- **MINOR**: compatible additions (new optional fields, new evidence sources).
- The version is defined in a single source: `src/apoch/public_api/version.py` as `API_VERSION`.
- The API version is independent of the project version (`__version__` in `apoch/__init__.py`).

### 1.2 What is out of scope

- Semantic versioning for the project itself (follows SemVer independently).
- API changelog (covered by the project CHANGELOG).

---

## 2. Current Version

`API_VERSION = "1.0"`

---

## 3. Consequences

- Incrementing `API_VERSION` requires updating `version.py` and any documentation that references it.
- Clients should check `api_version` first before parsing response fields.
- The field is always first in the response dict for easy client-side detection.
