"""Global error catalog for the public MCP API.

All public tools use EXCLUSIVELY these error codes. No custom or
module-specific codes are allowed in public responses.

Design: ADR-004 (error codes)
Spec: mcp-public-api §Catálogo Global de Códigos de Error
"""

from typing import Any

# ── Error codes ──────────────────────────────────────────────────────────────

ERR_TIMEOUT: str = "ERR_TIMEOUT"
"""Module did not respond within the configured timeout."""

ERR_NO_DATA: str = "ERR_NO_DATA"
"""No data available to answer the query."""

ERR_NOT_INITIALIZED: str = "ERR_NOT_INITIALIZED"
"""The system has not been started yet."""

ERR_DEPENDENCY_UNAVAILABLE: str = "ERR_DEPENDENCY_UNAVAILABLE"
"""A required internal module is not loaded or has failed."""

ERR_PERMISSION_DENIED: str = "ERR_PERMISSION_DENIED"
"""The caller does not have permission for this operation."""

ERR_INVALID_ARGUMENT: str = "ERR_INVALID_ARGUMENT"
"""One or more arguments are invalid or out of range."""

ERR_INTERNAL: str = "ERR_INTERNAL"
"""Unexpected internal error that could not be categorized."""

ERR_UNKNOWN: str = "ERR_UNKNOWN"
"""Unclassified error — last resort, always investigate."""

ERR_NOT_IMPLEMENTED: str = "ERR_NOT_IMPLEMENTED"
"""The requested tool functionality has not been implemented yet."""


# ── Error response builder ───────────────────────────────────────────────────


def error_response(code: str, message: str) -> dict[str, Any]:
    """Build a standard error response dict.

    Returns the envelope defined in the spec:
    ``{"ok": False, "error": {"code": "<code>", "message": "<message>"}}``

    Args:
        code: One of the ``ERR_*`` constants from this module.
        message: Human-readable error description.

    Returns:
        Dict ready for MCP serialization.
    """
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
