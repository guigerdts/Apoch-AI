"""ApochCoordinator — orchestrates internal modules for public MCP tools.

Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)
Spec: mcp-public-api §ToolResponse format, §Catálogo Global de Códigos de Error

Architecture constraints:
- No business logic: the coordinator only queries, aggregates, and responds.
- No concrete module knowledge: all communication via duck-typed services.
- No circular imports: coordinator imports models/registry/errors/version only.
- ToolResponse-only output: every public method returns a structured dict.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from apoch.public_api.errors import error_response
from apoch.public_api.models import EvidenceSource
from apoch.public_api.registry import ServiceRegistry
from apoch.public_api.version import API_VERSION

# ── Default timeouts (seconds per module) ─────────────────────────────────
# Configurable at module level — override via subclass or instance attr.
DEFAULT_TIMEOUTS: dict[str, float] = {
    "vision": 1.0,
    "guardian": 0.5,
    "chronicle": 0.5,
    "oracle": 2.0,
    "pulse": 0.5,
    "optimizer": 1.0,
}

# ── Confidence labels ─────────────────────────────────────────────────────
_CONFIDENCE_RANGES: list[tuple[float, str]] = [
    (0.90, "VERY_HIGH"),
    (0.75, "HIGH"),
    (0.50, "MEDIUM"),
    (0.25, "LOW"),
    (0.00, "VERY_LOW"),
]


class ApochCoordinator:
    """Coordina módulos internos para producir respuestas de herramientas públicas.

    7 métodos públicos, cada uno orquesta, agrega y devuelve ToolResponse.
    Sin estado entre llamadas. Todos los timeouts en segundos.
    """

    def __init__(
        self,
        services: ServiceRegistry,
        timeouts: dict[str, float] | None = None,
    ) -> None:
        self._services = services
        self._timeouts: dict[str, float] = timeouts or dict(DEFAULT_TIMEOUTS)

    # ── Internal: Module query engine ─────────────────────────────────────

    async def _query_modules(
        self,
        queries: list[tuple[str, Any, float]],
    ) -> dict[str, Any]:
        """Execute N module queries in parallel with individual timeouts.

        Each tuple is ``(name, coroutine, timeout_s)``. Modules that time
        out or raise get ``None`` in the result dict. No global timeout.
        """
        results: dict[str, Any] = {}

        async def _query_one(name: str, coro: Any, timeout: float) -> None:
            try:
                results[name] = await asyncio.wait_for(coro, timeout=timeout)
            except (TimeoutError, Exception):
                results[name] = None

        tasks = [_query_one(n, c, t) for n, c, t in queries]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    # ── Internal: Confidence calculation ──────────────────────────────────

    @staticmethod
    def _calculate_confidence(results: dict[str, Any]) -> float:
        """Weighted average: available (non-None) / total queried."""
        if not results:
            return 0.0
        available = sum(1 for v in results.values() if v is not None)
        return round(available / len(results), 2)

    @staticmethod
    def _confidence_label(confidence: float) -> str:
        """Map a numeric confidence to a human-readable label."""
        for threshold, label in _CONFIDENCE_RANGES:
            if confidence >= threshold:
                return label
        return "VERY_LOW"

    # ── Internal: Evidence building ──────────────────────────────────────

    @staticmethod
    def _build_evidence(results: dict[str, Any]) -> list[EvidenceSource]:
        """Build evidence list from module results, skipping None values.

        Each key is used as the evidence source name (capitalized).
        """
        evidence: list[EvidenceSource] = []
        for key, value in results.items():
            if value is not None:
                evidence.append(
                    EvidenceSource(
                        source=key.capitalize(),
                        confidence=0.8,
                        collected_ago=0,
                        based_on="module response",
                    )
                )
        return evidence

    # ── Internal: Response building ──────────────────────────────────────

    def _build_success_response(
        self,
        results: dict[str, Any],
        summary: str,
        explanation: str,
        suggested_action: str | None = None,
    ) -> dict[str, Any]:
        """Build a successful ToolResponse-compatible dict."""
        now = datetime.now(UTC)
        evidence = self._build_evidence(results)
        confidence = self._calculate_confidence(results)
        return {
            "api_version": API_VERSION,
            "summary": summary,
            "explanation": explanation,
            "evidence": [e.to_dict() for e in evidence],
            "suggested_action": suggested_action,
            "confidence": confidence,
            "generated_at": now.isoformat(),
            "data_freshness": 0,
            "metadata": {},
        }

    @staticmethod
    def _build_error_response(code: str, message: str) -> dict[str, Any]:
        """Build a standard error response dict from the error catalog."""
        return error_response(code, message)

    # ── Public tools (stubs — return ERR_NOT_IMPLEMENTED) ─────────────────
    # ── Business logic will be implemented in PR2 through PR8.

    async def status(self) -> dict[str, Any]:
        """General system status — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")

    async def history(
        self,
        horas: int | None = None,  # noqa: ARG002
        tipo: str | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Chronological timeline — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")

    async def health(self) -> dict[str, Any]:
        """Interpreted diagnostics — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")

    async def recommend(self) -> dict[str, Any]:
        """Next action recommendation — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")

    async def progress(
        self,
        periodo: str | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Productivity and trends — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")

    async def insights(self) -> dict[str, Any]:
        """Patterns and improvement opportunities — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")

    async def logs(
        self,
        nivel: str | None = None,  # noqa: ARG002
        limite: int | None = None,  # noqa: ARG002
        modulo: str | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Technical logs — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")
