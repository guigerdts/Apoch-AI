"""API version constant for the public MCP API.

Follows MAJOR.MINOR versioning. Increments per ADR-005:
- MAJOR: breaking changes (removing/renaming required fields)
- MINOR: compatible additions (new optional fields, evidence sources)

Design: ADR-005 (Versionado de la API)
"""

API_VERSION: str = "1.0"
"""Current version of the public MCP API contract."""
