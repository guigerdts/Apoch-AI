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
from datetime import UTC, datetime, timedelta
from typing import Any

from apoch.adapters.base import ToolDef
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

# ── Status query constants ────────────────────────────────────────────────
STATUS_RECENT_EVENTS_LIMIT: int = 5
STATUS_RECENT_WINDOW_MINUTES: int = 5

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
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Build a successful ToolResponse-compatible dict.

        If *confidence* is provided, it is used directly. Otherwise it is
        calculated from *results* via ``_calculate_confidence()``.
        """
        now = datetime.now(UTC)
        evidence = self._build_evidence(results)
        if confidence is None:
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

    # ── Tool definition registration ─────────────────────────────────────

    @classmethod
    def get_tool_defs(cls) -> list[ToolDef]:
        """Return the ToolDefs for all implemented public tools (progressive registration).

        PR2: apoch_status
        PR3: apoch_health
        Future PRs add one tool at a time.
        Only fully implemented tools are registered — no stubs visible.
        """
        return [
            ToolDef(
                name="apoch_status",
                description=(
                    "Estado general del sistema: componentes activos, "
                    "problemas detectados y actividad reciente."
                ),
                input_schema={"type": "object", "properties": {}},
                handler_name="status",
            ),
            ToolDef(
                name="apoch_health",
                description=(
                    "Diagnóstico del sistema: problemas activos, su severidad, "
                    "posible causa y acción recomendada."
                ),
                input_schema={"type": "object", "properties": {}},
                handler_name="health",
            ),
        ]

    async def status(self) -> dict[str, Any]:
        """General system status — orchestrate Vision, Guardian, Chronicle, Oracle.

        Builds a unified view: active components, detected problems, recent
        activity, and a quick recommendation (if Oracle responds).

        Spec: mcp-public-api §Tool 1: apoch_status, §Niveles de Confianza
        Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)
        """
        queries: list[tuple[str, Any, float]] = []

        # Vision — module_state() (mandatory)
        if self._services.vision is not None and hasattr(self._services.vision, "module_state"):
            queries.append((
                "vision",
                self._services.vision.module_state(),
                self._timeouts.get("vision", 1.0),
            ))

        # Guardian — all_diagnostics() (mandatory)
        if (self._services.guardian is not None
                and hasattr(self._services.guardian, "all_diagnostics")):
            queries.append((
                "guardian",
                self._services.guardian.all_diagnostics(),
                self._timeouts.get("guardian", 0.5),
            ))

        # Chronicle — query() with recent events limit AND window (mandatory)
        if self._services.chronicle is not None and hasattr(self._services.chronicle, "query"):
            window = timedelta(minutes=STATUS_RECENT_WINDOW_MINUTES)
            since = (datetime.now(UTC) - window).isoformat()
            queries.append((
                "chronicle",
                self._services.chronicle.query(since=since, limit=STATUS_RECENT_EVENTS_LIMIT),
                self._timeouts.get("chronicle", 0.5),
            ))

        # Oracle — status/recommend (optional)
        if self._services.oracle is not None and hasattr(self._services.oracle, "status"):
            queries.append((
                "oracle",
                self._services.oracle.status(),
                self._timeouts.get("oracle", 2.0),
            ))

        results = await self._query_modules(queries)

        # Unpack module results.
        vision_data = results.get("vision")
        guardian_data = results.get("guardian")
        chronicle_data = results.get("chronicle")
        oracle_data = results.get("oracle")

        # Determine overall state.
        has_problems = False
        if guardian_data is not None and isinstance(guardian_data, dict):
            diagnostics = guardian_data.get("diagnostics", []) or []
            has_problems = any(
                d.get("severity") in ("ERROR", "CRITICAL") for d in diagnostics
            )

        all_mandatory = all(
            results.get(m) is not None for m in ("vision", "guardian", "chronicle")
        )
        no_data = all(v is None for v in results.values())

        if no_data:
            return self._build_error_response("ERR_TIMEOUT", "No modules responded")

        if has_problems:
            summary = "🔴 Sistema operativo con problemas detectados"
        elif not all_mandatory:
            summary = "🟡 Sistema funcionando con limitaciones"
        else:
            summary = "🟢 Todos los sistemas operativos"

        # Build explanation.
        parts: list[str] = []
        if vision_data is not None:
            items_count = (
                len(vision_data)
                if isinstance(vision_data, (list, dict))
                else 0
            )
            if items_count:
                parts.append(f"{items_count} componentes activos")
            else:
                parts.append("Componentes activos")
        if has_problems:
            parts.append("problemas detectados")
        elif guardian_data is not None:
            parts.append("sin errores")
        if chronicle_data is not None:
            if isinstance(chronicle_data, (list, dict)) and not chronicle_data:
                parts.append("sin actividad registrada")
            else:
                parts.append("actividad reciente disponible")
        else:
            parts.append("sin datos de actividad reciente")

        explanation = " — ".join(parts) if parts else "Estado general del sistema"

        # Determine suggested_action.
        if oracle_data is not None:
            suggested_action = (
                oracle_data.get("suggested_action")
                or "Ninguna acción requerida"
            )
        elif has_problems:
            suggested_action = "Revise los problemas detectados"
        else:
            suggested_action = "Ninguna acción requerida"

        return self._build_success_response(
            results=results,
            summary=summary,
            explanation=explanation,
            suggested_action=suggested_action,
        )

    async def history(
        self,
        horas: int | None = None,  # noqa: ARG002
        tipo: str | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Chronological timeline — stubbed."""
        return self._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")

    async def health(self) -> dict[str, Any]:
        """Diagnose system health — classify problems via Guardian, enrich with Vision.

        Spec: mcp-public-api §Tool 2: apoch_health
        Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

        Boundaries (see apoch_health-boundary-review.md):
        - NEVER recommends actions (belongs to recommend)
        - NEVER shows history (belongs to history)
        - NEVER interprets productivity or patterns (belongs to progress/insights)
        - Action per problem = micro-action for THAT problem, not prioritization
        - Guardian is authoritative for diagnostics. Vision enriches but does not define.
        - Confidence: HIGH when both respond; MEDIUM when Guardian only.
        """
        queries: list[tuple[str, Any, float]] = []

        # Guardian — all_diagnostics() (mandatory — health's purpose)
        if (self._services.guardian is not None
                and hasattr(self._services.guardian, "all_diagnostics")):
            queries.append((
                "guardian",
                self._services.guardian.all_diagnostics(),
                self._timeouts.get("guardian", 0.5),
            ))

        # Vision — module_state() (optional — enrichment)
        if self._services.vision is not None and hasattr(self._services.vision, "module_state"):
            queries.append((
                "vision",
                self._services.vision.module_state(),
                self._timeouts.get("vision", 1.0),
            ))

        results = await self._query_modules(queries)
        guardian_data = results.get("guardian")
        vision_data = results.get("vision")

        # If Guardian fails, health cannot produce a diagnosis
        if guardian_data is None:
            if vision_data is not None:
                explanation = (
                    "No se pudo obtener diagnóstico del sistema. "
                    "Componentes activos pero sin información de salud."
                )
            else:
                explanation = "No se pudo obtener diagnóstico del sistema."
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                explanation,
            )

        # Parse diagnostics from Guardian
        diagnostics: list[dict] = []
        if isinstance(guardian_data, dict):
            diagnostics = guardian_data.get("diagnostics", []) or []

        # Classify severity
        has_critical = any(
            d.get("severity") in ("ERROR", "CRITICAL") for d in diagnostics
        )
        has_warning = any(
            d.get("severity") == "WARNING" for d in diagnostics
        )

        # Build summary
        if has_critical:
            summary = "🔴 Se detectaron problemas críticos en el sistema"
        elif has_warning:
            summary = "🟡 Se detectaron advertencias en el sistema"
        else:
            summary = "🟢 Sin problemas detectados"

        # Build explanation with per-problem details
        parts: list[str] = []
        if diagnostics:
            # Sort: most severe first
            severity_order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2}
            sorted_diags = sorted(
                diagnostics,
                key=lambda d: severity_order.get(d.get("severity", ""), 99),
            )
            for diag in sorted_diags:
                sev = diag.get("severity", "UNKNOWN")
                module = diag.get("module", "desconocido")
                msg = diag.get("message", "")
                parts.append(f"[{sev}] {module}: {msg}")
        elif vision_data is not None:
            parts.append("No hay problemas registrados en el sistema")
        else:
            parts.append("No hay problemas registrados")

        explanation = "\n".join(parts)

        # Build suggested_action from most severe problem
        if diagnostics:
            severity_order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2}
            sorted_diags = sorted(
                diagnostics,
                key=lambda d: severity_order.get(d.get("severity", ""), 99),
            )
            worst = sorted_diags[0]
            sev = worst.get("severity", "")
            module = worst.get("module", "")
            if sev in ("ERROR", "CRITICAL"):
                suggested_action = (
                    f"Revise el módulo {module}. "
                    f"Puede intentar reiniciar el módulo o revisar su configuración."
                )
            elif sev == "WARNING":
                suggested_action = (
                    f"Revise la advertencia en {module} "
                    f"para evitar que evolucione a un problema crítico."
                )
            else:
                suggested_action = "Ninguna acción requerida"
        else:
            suggested_action = "Ninguna acción requerida"

        # Confidence: expected = 2 (guardian + vision), available = those that
        # actually responded. This ensures MEDIUM when only Guardian responds.
        n_expected = 2
        n_available = sum(1 for v in results.values() if v is not None)
        health_confidence = round(n_available / n_expected, 2)

        return self._build_success_response(
            results=results,
            summary=summary,
            explanation=explanation,
            suggested_action=suggested_action,
            confidence=health_confidence,
        )

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
