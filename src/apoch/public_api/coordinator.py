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
import functools
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from apoch.adapters.base import ToolDef
from apoch.core.events import EventBus, EventTopics, SystemEvent
from apoch.public_api.errors import error_response
from apoch.public_api.models import EvidenceSource
from apoch.public_api.registry import ServiceRegistry
from apoch.public_api.version import API_VERSION

_F = TypeVar("_F", bound=Callable[..., Any])

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

# ── History query constants ──────────────────────────────────────────────
HISTORY_DEFAULT_HOURS: int = 24
HISTORY_DEFAULT_LIMIT: int = 50
HISTORY_MAX_LIMIT: int = 200

# ── Progress query constants ─────────────────────────────────────────────
_PROGRESS_PERIODOS: frozenset[str] = frozenset({"hoy", "semana", "mes"})
_PROGRESS_DAYS: dict[str, int] = {
    "hoy": 1,
    "semana": 7,
    "mes": 30,
}
_PROGRESS_TREND_WINDOW: dict[str, int] = {
    "hoy": 1,
    "semana": 3,
    "mes": 15,
}
_PROGRESS_LOW_THRESHOLD: int = 3

# ── Logs query constants ────────────────────────────────────────────────
LOGS_DEFAULT_LIMIT: int = 50
LOGS_VISION_TIMEOUT: float = 0.5
_LOGS_VALID_LEVELS: frozenset[str] = frozenset({"INFO", "WARN", "ERROR", "FATAL"})

# ── History type mapping ─────────────────────────────────────────────────
_TYPE_MAP: dict[str, str] = {
    "tool": "tool_invocation",
}

# ── Source aliases (user-facing, no module names) ────────────────────────
_SOURCE_ALIASES: dict[str, str] = {
    "vision": "Sistema de monitoreo",
    "chronicle": "Sistema de registro",
    "guardian": "Sistema de diagnóstico",
    "oracle": "Sistema de recomendaciones",
    "pulse": "Sistema de rendimiento",
    "optimizer": "Optimizador",
    "manager": "Gestor de módulos",
    "api": "API del sistema",
}
_SOURCE_DEFAULT: str = "Módulo del sistema"

# ── Priority mapping: Oracle → RecommendResponse ──────────────────────────
_ORACLE_PRIORITY_MAP: dict[str, str] = {
    "critical": "HIGH",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}

# ── Fallback priority: Guardian severity → RecommendResponse ──────────────
_FALLBACK_SEVERITY_MAP: dict[str, str] = {
    "ERROR": "HIGH",
    "CRITICAL": "HIGH",
    "WARNING": "MEDIUM",
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
        event_bus: EventBus | None = None,
    ) -> None:
        self._services = services
        self._timeouts: dict[str, float] = timeouts or dict(DEFAULT_TIMEOUTS)
        self._event_bus: EventBus | None = event_bus

    # ── Internal: Tool event emission ─────────────────────────────────────

    async def _emit_tool_event(self, topic: str, tool_name: str, **extra: Any) -> None:
        """Emit a tool-related SystemEvent if event_bus is set.

        No-op when ``self._event_bus`` is ``None`` (backward compatible).
        """
        if self._event_bus is None:
            return
        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=topic,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": tool_name, **extra},
        )
        await self._event_bus.emit(event)

    async def _emit_tool_result(self, tool_name: str, response: dict[str, Any]) -> dict[str, Any]:
        """Emit TOOL_COMPLETED or TOOL_ERROR based on *response*.

        Helper that emits the appropriate completion event and returns
        the response unchanged.  No-op when ``self._event_bus`` is ``None``.
        """
        if self._event_bus is not None:
            if response.get("error"):
                await self._emit_tool_event(
                    EventTopics.TOOL_ERROR,
                    tool_name,
                    code=response["error"].get("code", "ERR_UNKNOWN"),
                )
            else:
                await self._emit_tool_event(EventTopics.TOOL_COMPLETED, tool_name)
        return response

    @staticmethod
    def _auto_emit_tool_events(method: _F) -> _F:
        """Decorator: auto-emit TOOL_INVOCATION + TOOL_COMPLETED/TOOL_ERROR.

        Wraps any public tool method so invocation and completion/error
        events are emitted automatically.  No-op when event_bus is None
        (handled inside _emit_tool_event / _emit_tool_result).
        """
        tool_name = method.__name__

        @functools.wraps(method)
        async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            await self._emit_tool_event(EventTopics.TOOL_INVOCATION, tool_name)
            result = await method(self, *args, **kwargs)
            return await self._emit_tool_result(tool_name, result)

        return wrapper  # type: ignore[return-value]

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

    # ── Internal: Guardian diagnostics parser (shared) ────────────────────

    @staticmethod
    def _parse_guardian_diagnostics(
        guardian_data: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        """Parse Guardian ``all_diagnostics()`` into normalized problem dicts.

        Returns a list of dicts with keys: ``severity`` (ERROR|WARNING),
        ``module`` (str), ``message`` (str). Empty list = no problems.

        Real ``GuardianModule.all_diagnostics()`` returns
        ``dict[str, ModuleDiagnostics]`` keyed by module name, where each
        ``ModuleDiagnostics`` has ``current_state``, ``last_error``, etc.

        Mapping:
        - ``current_state == "FAILED"`` → severity ``ERROR``
        - ``last_error`` is set (non-FAILED) → severity ``WARNING``
        - Everything else → skipped (no active issue).
        """
        if not guardian_data:
            return []

        problems: list[dict[str, str]] = []
        for module_name, diag in guardian_data.items():
            # Duck-type guard: only process ModuleDiagnostics-like objects
            if not hasattr(diag, "current_state"):
                continue

            state: str = diag.current_state
            if state == "FAILED":
                severity: str = "ERROR"
            elif diag.last_error is not None:
                severity = "WARNING"
            else:
                continue  # no active issue

            message: str = diag.last_error or (f"Module {module_name} is in {state} state")
            problems.append(
                {
                    "severity": severity,
                    "module": module_name,
                    "message": message,
                }
            )

        return problems

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
        priority: str | None = None,
        expected_benefit: str | None = None,
    ) -> dict[str, Any]:
        """Build a successful ToolResponse-compatible dict.

        If *confidence* is provided, it is used directly. Otherwise it is
        calculated from *results* via ``_calculate_confidence()``.

        When *priority* is provided, the response becomes a
        ``RecommendResponse`` with the additional fields.
        """
        now = datetime.now(UTC)
        evidence = self._build_evidence(results)
        if confidence is None:
            confidence = self._calculate_confidence(results)

        resp: dict[str, Any] = {
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
        if priority is not None:
            resp["priority"] = priority
        if expected_benefit is not None:
            resp["expected_benefit"] = expected_benefit
        return resp

    @staticmethod
    def _build_error_response(code: str, message: str) -> dict[str, Any]:
        """Build a standard error response dict from the error catalog."""
        return error_response(code, message)

    # ── Tool definition registration ─────────────────────────────────────

    @classmethod
    def get_tool_defs(cls) -> list[ToolDef]:
        """Return the ToolDefs for all implemented public tools (progressive registration).

        PR2: apoch_status
        PR3: apoch_health
        PR4: apoch_history
        PR5: apoch_recommend
        PR6: apoch_progress
        PR7: apoch_insights
        PR8: apoch_logs
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
            ToolDef(
                name="apoch_history",
                description=(
                    "Historial cronológico de actividad del sistema: "
                    "eventos recientes, filtros por horas y tipo, "
                    "con resumen contextual."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "horas": {
                            "type": "integer",
                            "description": ("Últimas N horas a consultar (default: 24)"),
                        },
                        "tipo": {
                            "type": "string",
                            "enum": ["lifecycle", "tool", "error"],
                            "description": ("Filtro por tipo de evento: lifecycle, tool, error"),
                        },
                    },
                },
                handler_name="history",
            ),
            ToolDef(
                name="apoch_recommend",
                description=(
                    "Recomendación de la siguiente acción de mayor impacto "
                    "sobre la plataforma Apoch-AI."
                ),
                input_schema={"type": "object", "properties": {}},
                handler_name="recommend",
            ),
            ToolDef(
                name="apoch_progress",
                description=(
                    "Productividad, evolución y tendencias interpretadas "
                    "basadas en datos de actividad del sistema."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "periodo": {
                            "type": "string",
                            "enum": ["hoy", "semana", "mes"],
                            "description": (
                                "Periodo a consultar: None (últimas 24h), hoy, semana, mes"
                            ),
                        },
                    },
                },
                handler_name="progress",
            ),
            ToolDef(
                name="apoch_insights",
                description=(
                    "Patrones detectados y oportunidades de mejora "
                    "basados en datos de optimización del sistema."
                ),
                input_schema={"type": "object", "properties": {}},
                handler_name="insights",
            ),
            ToolDef(
                name="apoch_logs",
                description=(
                    "Logs técnicos del sistema para depuración: entradas "
                    "filtrables por nivel, módulo y límite."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "nivel": {
                            "type": "string",
                            "enum": ["INFO", "WARN", "ERROR", "FATAL"],
                            "description": "Filtro por nivel de severidad.",
                        },
                        "limite": {
                            "type": "integer",
                            "description": ("Máximo de entradas a devolver (default: 50)."),
                        },
                        "modulo": {
                            "type": "string",
                            "description": ("Filtro por módulo (aplica en memoria)."),
                        },
                    },
                },
                handler_name="logs",
            ),
        ]

    # ── Legacy alias registration (PR9 — backward compatibility) ─────────

    @classmethod
    def get_legacy_aliases(cls) -> list[ToolDef]:
        """Return ToolDefs for legacy backward-compatibility aliases.

        Each alias delegates to the same public tool handler, with
        deprecation metadata injected by the wrapper method.

        PR9: vision_state→apoch_status, chronicle_query→apoch_history,
             guardian_diagnostics→apoch_health,
             guardian_all_diagnostics→apoch_health,
             vision_logs→apoch_logs

        Returns:
            List of 5 ToolDef entries pointing to ``legacy_*`` handlers.
        """
        return [
            ToolDef(
                name="vision_state",
                description=(
                    "[DEPRECATED] Use apoch_status instead. "
                    "Return current states of loaded modules."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "module": {
                            "type": "string",
                            "description": "Optional module name. Omit for all.",
                        },
                    },
                },
                handler_name="legacy_vision_state",
            ),
            ToolDef(
                name="chronicle_query",
                description=(
                    "[DEPRECATED] Use apoch_history instead. Query recorded activity events."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Optional source filter.",
                        },
                        "event_type": {
                            "type": "string",
                            "description": "Optional event type filter.",
                        },
                        "since": {
                            "type": "string",
                            "format": "date-time",
                            "description": "ISO 8601 start timestamp.",
                        },
                        "until": {
                            "type": "string",
                            "format": "date-time",
                            "description": "ISO 8601 end timestamp.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results.",
                            "default": 100,
                        },
                    },
                },
                handler_name="legacy_chronicle_query",
            ),
            ToolDef(
                name="guardian_diagnostics",
                description=(
                    "[DEPRECATED] Use apoch_health instead. "
                    "Return diagnostics for a specific module."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "module_name": {
                            "type": "string",
                            "description": "Name of the module to inspect.",
                        },
                    },
                    "required": ["module_name"],
                },
                handler_name="legacy_guardian_diagnostics",
            ),
            ToolDef(
                name="guardian_all_diagnostics",
                description=(
                    "[DEPRECATED] Use apoch_health instead. "
                    "Return diagnostics for all tracked modules."
                ),
                input_schema={"type": "object", "properties": {}},
                handler_name="legacy_guardian_all_diagnostics",
            ),
            ToolDef(
                name="vision_logs",
                description=(
                    "[DEPRECATED] Use apoch_logs instead. Return recent structured log entries."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max entries (default 50).",
                        },
                        "level": {
                            "type": "string",
                            "description": "Severity filter (e.g. ERROR).",
                        },
                    },
                },
                handler_name="legacy_vision_logs",
            ),
        ]

    @_auto_emit_tool_events
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
            queries.append(
                (
                    "vision",
                    self._services.vision.module_state(),
                    self._timeouts.get("vision", 1.0),
                )
            )

        # Guardian — all_diagnostics() (mandatory)
        if self._services.guardian is not None and hasattr(
            self._services.guardian, "all_diagnostics"
        ):
            queries.append(
                (
                    "guardian",
                    self._services.guardian.all_diagnostics(),
                    self._timeouts.get("guardian", 0.5),
                )
            )

        # Chronicle — query() with recent events limit AND window (mandatory)
        if self._services.chronicle is not None and hasattr(self._services.chronicle, "query"):
            window = timedelta(minutes=STATUS_RECENT_WINDOW_MINUTES)
            since = (datetime.now(UTC) - window).isoformat()
            queries.append(
                (
                    "chronicle",
                    self._services.chronicle.query(since=since, limit=STATUS_RECENT_EVENTS_LIMIT),
                    self._timeouts.get("chronicle", 0.5),
                )
            )

        # Oracle — status/recommend (optional)
        if self._services.oracle is not None and hasattr(self._services.oracle, "status"):
            queries.append(
                (
                    "oracle",
                    self._services.oracle.status(),
                    self._timeouts.get("oracle", 2.0),
                )
            )

        results = await self._query_modules(queries)

        # Unpack module results.
        vision_data = results.get("vision")
        guardian_data = results.get("guardian")
        chronicle_data = results.get("chronicle")
        oracle_data = results.get("oracle")

        # Determine overall state (shared parser — real ModuleDiagnostics format).
        status_diagnostics = self._parse_guardian_diagnostics(guardian_data)
        has_problems = any(d.get("severity") in ("ERROR", "CRITICAL") for d in status_diagnostics)

        all_mandatory = all(results.get(m) is not None for m in ("vision", "guardian", "chronicle"))
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
            items_count = len(vision_data) if isinstance(vision_data, (list, dict)) else 0
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
            suggested_action = oracle_data.get("suggested_action") or "Ninguna acción requerida"
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

    @_auto_emit_tool_events
    async def history(
        self,
        horas: int | None = None,
        tipo: str | None = None,
    ) -> dict[str, Any]:
        """Chronological timeline — natural language narrative.

        Spec: mcp-public-api §Tool 2: apoch_history
        Design: ADR-001, ADR-004, ADR-007

        Boundaries:
        - Single module dependency: Chronicle is REQUIRED
        - Vision is NOT consulted in PR4 (deferred per boundary review)
        - NEVER: trends, metrics, global aggregations, period comparison
        - NEVER: event interpretation, recommendations, diagnosis
        - NEVER: Pulse/Progress/Insights replacement
        - suggested_action is always None (pure query)
        """
        # ── Validate parameters ──────────────────────────────────────────
        if horas is not None and (not isinstance(horas, int) or horas <= 0):
            return self._build_error_response(
                "ERR_INVALID_ARGUMENT",
                "horas debe ser un entero positivo",
            )
        if tipo is not None and tipo not in ("lifecycle", "tool", "error"):
            return self._build_error_response(
                "ERR_INVALID_ARGUMENT",
                "tipo debe ser uno de: lifecycle, tool, error",
            )

        # ── Calculate time window ────────────────────────────────────────
        horas = horas or HISTORY_DEFAULT_HOURS
        since = (datetime.now(UTC) - timedelta(hours=horas)).isoformat()
        limit = HISTORY_DEFAULT_LIMIT

        # ── Query Chronicle ──────────────────────────────────────────────
        queries: list[tuple[str, Any, float]] = []
        if self._services.chronicle is not None and hasattr(self._services.chronicle, "query"):
            from apoch.modules.chronicle.models import EventFilter  # noqa: PLC0415

            ef: EventFilter | None = None
            if tipo:
                chronicle_type = _TYPE_MAP.get(tipo, tipo)
                ef = EventFilter(type=chronicle_type)

            queries.append(
                (
                    "chronicle",
                    self._services.chronicle.query(
                        event_filter=ef,
                        since=since,
                        limit=limit,
                    ),
                    self._timeouts.get("chronicle", 0.5),
                )
            )

        results = await self._query_modules(queries)
        chronicle_data = results.get("chronicle")

        # ── Handle unavailable Chronicle ─────────────────────────────────
        if chronicle_data is None:
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                "No se pudo consultar el historial de actividad",
            )

        # ── Ensure it's a list ───────────────────────────────────────────
        events = chronicle_data if isinstance(chronicle_data, list) else []

        # ── Build narrative and counts ───────────────────────────────────
        if not events:
            summary = "No hay actividad registrada en el período solicitado."
            explanation = summary
            confidence = 0.30
            based_on = "0 events"
        else:
            lines: list[str] = []
            type_counts: dict[str, int] = {
                "lifecycle": 0,
                "tool": 0,
                "error": 0,
            }

            for event in events:
                time_part = event.timestamp[11:16]
                source_alias = _SOURCE_ALIASES.get(
                    event.source,
                    _SOURCE_DEFAULT,
                )

                if event.type == "lifecycle":
                    status = event.payload.get("status", "operativo")
                    lines.append(f"{time_part} — {source_alias} {status}")
                elif event.type == "tool_invocation":
                    tool_name = event.payload.get("tool", "herramienta")
                    lines.append(
                        f"{time_part} — Herramienta invocada: {tool_name}",
                    )
                elif event.type == "error":
                    msg = event.payload.get("message", "")
                    if msg:
                        lines.append(f"{time_part} — Error: {msg}")
                    else:
                        lines.append(f"{time_part} — Error en {source_alias}")

                # Count by public-facing type
                reverse_map = {v: k for k, v in _TYPE_MAP.items()}
                public_type = reverse_map.get(event.type, event.type)
                if public_type in type_counts:
                    type_counts[public_type] += 1

            explanation = "\n".join(lines)

            counts_str = ", ".join(
                f"{key}: {count}" for key, count in type_counts.items() if count > 0
            )
            if counts_str:
                summary = (
                    f"Se encontraron {len(events)} eventos "
                    f"({counts_str}) en las últimas {horas} horas"
                )
            else:
                summary = f"Se encontraron {len(events)} eventos en las últimas {horas} horas"
            confidence = 0.50
            based_on = f"{len(events)} events"

        # ── Build evidence ──────────────────────────────────────────────
        evidence_entry = EvidenceSource(
            source="Chronicle",
            confidence=0.8,
            collected_ago=0,
            based_on=based_on,
        )

        # ── Build response ──────────────────────────────────────────────
        now = datetime.now(UTC)
        return {
            "api_version": API_VERSION,
            "summary": summary,
            "explanation": explanation,
            "evidence": [evidence_entry.to_dict()],
            "suggested_action": None,
            "confidence": confidence,
            "generated_at": now.isoformat(),
            "data_freshness": 0,
            "metadata": {},
        }

    @_auto_emit_tool_events
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
        if self._services.guardian is not None and hasattr(
            self._services.guardian, "all_diagnostics"
        ):
            queries.append(
                (
                    "guardian",
                    self._services.guardian.all_diagnostics(),
                    self._timeouts.get("guardian", 0.5),
                )
            )

        # Vision — module_state() (optional — enrichment)
        if self._services.vision is not None and hasattr(self._services.vision, "module_state"):
            queries.append(
                (
                    "vision",
                    self._services.vision.module_state(),
                    self._timeouts.get("vision", 1.0),
                )
            )

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
            return await self._emit_tool_result(
                "health",
                self._build_error_response(
                    "ERR_DEPENDENCY_UNAVAILABLE",
                    explanation,
                ),
            )

        # Parse diagnostics from Guardian (shared parser — real ModuleDiagnostics format)
        diagnostics: list[dict[str, str]] = self._parse_guardian_diagnostics(guardian_data)

        # Classify severity
        has_critical = any(d.get("severity") in ("ERROR", "CRITICAL") for d in diagnostics)
        has_warning = any(d.get("severity") == "WARNING" for d in diagnostics)

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

        # Compute healthy boolean for the response contract (BUG-002).
        healthy = not has_critical

        resp = self._build_success_response(
            results=results,
            summary=summary,
            explanation=explanation,
            suggested_action=suggested_action,
            confidence=health_confidence,
        )
        resp["healthy"] = healthy
        return resp

    @_auto_emit_tool_events
    async def recommend(self) -> dict[str, Any]:
        """Next action recommendation over the Apoch-AI platform.

        Spec: mcp-public-api §Tool 4: apoch_recommend
        Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

        Flow (per Architecture Decision):
          1. Oracle available + recommendations → use rec #1
          2. Oracle available + empty list → fallback Guardian+Vision
          3. Oracle unavailable → fallback Guardian+Vision
          4. Guardian has problems → single recommendation from worst problem
          5. Guardian+Vision healthy → "No hay recomendaciones"
          6. All three modules fail → ERR_TIMEOUT
        """
        queries: list[tuple[str, Any, float]] = []

        # Oracle — recommendations (optional, primary source)
        oracle_queried = False
        recs_svc: Any = None
        if self._services.oracle is not None and hasattr(self._services.oracle, "services"):
            recs_svc = self._services.oracle.services.get("oracle.recommendations")  # type: ignore[union-attr]
            if recs_svc:
                oracle_queried = True

                async def _fetch_oracle_recs() -> Any:
                    result = recs_svc()
                    if asyncio.iscoroutine(result):
                        return await result
                    return result

                queries.append(
                    (
                        "oracle",
                        _fetch_oracle_recs(),
                        self._timeouts.get("oracle", 2.0),
                    )
                )

        # Guardian — diagnostics (optional, fallback)
        if self._services.guardian is not None and hasattr(
            self._services.guardian, "all_diagnostics"
        ):
            queries.append(
                (
                    "guardian",
                    self._services.guardian.all_diagnostics(),
                    self._timeouts.get("guardian", 0.5),
                )
            )

        # Vision — module_state (optional, fallback enrichment)
        if self._services.vision is not None and hasattr(self._services.vision, "module_state"):
            queries.append(
                (
                    "vision",
                    self._services.vision.module_state(),
                    self._timeouts.get("vision", 1.0),
                )
            )

        results = await self._query_modules(queries)
        oracle_data: Any = results.get("oracle")
        guardian_data = results.get("guardian")
        vision_data = results.get("vision")

        # TIMEOUT: no data from any module
        if all(v is None for v in results.values()):
            return self._build_error_response(
                "ERR_TIMEOUT",
                "No se pudo obtener información para generar una recomendación",
            )

        # CASE 1: Oracle available with recommendations
        if oracle_data is not None and isinstance(oracle_data, list) and len(oracle_data) > 0:
            rec = oracle_data[0]
            return self._build_recommend_response(
                summary=rec.title,
                explanation=rec.justification,
                confidence=rec.confidence,
                priority=self._map_oracle_priority(rec.priority),
                expected_benefit=None,
                evidence=self._build_recommend_evidence(
                    oracle_used=True,
                    guardian_data=guardian_data,
                    vision_data=vision_data,
                ),
            )

        # CASE 2: Fallback — Guardian + Vision
        diagnostics = self._parse_guardian_diagnostics(guardian_data)

        if diagnostics:
            severity_order = {"CRITICAL": 0, "ERROR": 0, "WARNING": 1}
            sorted_problems = sorted(
                diagnostics,
                key=lambda d: severity_order.get(d.get("severity", ""), 99),
            )
            worst = sorted_problems[0]
            sev: str = worst.get("severity", "ERROR")
            mod: str = worst.get("module", "módulo")
            msg: str = worst.get("message", "")

            priority = _FALLBACK_SEVERITY_MAP.get(sev, "MEDIUM")
            summary = f"Revisar módulo {mod}"
            explanation = f"[{sev}] {mod}: {msg}"
            confidence = 0.5

            return self._build_recommend_response(
                summary=summary,
                explanation=explanation,
                confidence=confidence,
                priority=priority,
                evidence=self._build_recommend_evidence(
                    guardian_used=True,
                    guardian_data=guardian_data,
                    vision_data=vision_data,
                ),
            )

        # CASE 3: No recommendations — everything looks healthy
        confidence = 0.85 if oracle_queried else 1.0
        return self._build_recommend_response(
            summary="No hay recomendaciones en este momento.",
            explanation="El sistema opera dentro de parámetros normales.",
            suggested_action=None,
            confidence=confidence,
            priority="LOW",
            evidence=self._build_recommend_evidence(
                oracle_used=oracle_queried,
                guardian_data=guardian_data,
                vision_data=vision_data,
            ),
        )

    @staticmethod
    def _map_oracle_priority(priority: str) -> str:
        """Map Oracle RecommendationPriority to RecommendResponse priority."""
        return _ORACLE_PRIORITY_MAP.get(priority, "MEDIUM")

    @staticmethod
    def _build_recommend_evidence(
        oracle_used: bool = False,
        guardian_used: bool = False,
        guardian_data: Any = None,
        vision_data: Any = None,
    ) -> list[dict[str, Any]]:
        """Build evidence list with functional labels (P6 for recommend).

        Uses descriptive functional labels instead of internal module names
        to comply with spec §1.7 (P6 — no exposed implementation).
        """
        evidence_sources: list[EvidenceSource] = []
        seen: set[str] = set()

        if oracle_used:
            evidence_sources.append(
                EvidenceSource(
                    source="Sistema de recomendaciones",
                    confidence=0.8,
                    collected_ago=0,
                    based_on="recomendación priorizada",
                )
            )
            seen.add("oracle")

        if guardian_data is not None:
            n_problems = len(
                [
                    d
                    for d in (guardian_data.values() if isinstance(guardian_data, dict) else [])
                    if hasattr(d, "current_state") and d.current_state == "FAILED"
                ]
            )
            based_on = (
                f"{n_problems} problema(s) activo(s)" if n_problems else "sin problemas detectados"
            )
            evidence_sources.append(
                EvidenceSource(
                    source="Diagnóstico del sistema",
                    confidence=0.7,
                    collected_ago=0,
                    based_on=based_on,
                )
            )
            seen.add("guardian")

        if vision_data is not None and "vision" not in seen:
            evidence_sources.append(
                EvidenceSource(
                    source="Estado de componentes",
                    confidence=0.6,
                    collected_ago=0,
                    based_on="estado de módulos",
                )
            )

        return [e.to_dict() for e in evidence_sources]

    def _build_recommend_response(
        self,
        summary: str,
        explanation: str,
        confidence: float,
        priority: str,
        evidence: list[dict[str, Any]] | None = None,
        expected_benefit: str | None = None,
        suggested_action: str | None = None,
    ) -> dict[str, Any]:
        """Build a RecommendResponse-compatible dict.

        Separate from ``_build_success_response`` because recommend needs:
        - ``priority`` field (always required)
        - Functional evidence labels (P6), not module-name-based
        - ``suggested_action`` is always ``None``
        """
        now = datetime.now(UTC)
        resp: dict[str, Any] = {
            "api_version": API_VERSION,
            "summary": summary,
            "explanation": explanation,
            "evidence": evidence or [],
            "suggested_action": suggested_action,
            "confidence": confidence,
            "priority": priority,
            "generated_at": now.isoformat(),
            "data_freshness": 0,
            "metadata": {},
        }
        if expected_benefit is not None:
            resp["expected_benefit"] = expected_benefit
        return resp

    @_auto_emit_tool_events
    async def progress(self, periodo: str | None = None) -> dict[str, Any]:
        """Productivity, evolution and interpreted trends.

        Spec: mcp-public-api §Tool 5: apoch_progress
        Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

        Boundaries (see spec §1.4, §1.9):
        - Single module dependency: Pulse is REQUIRED
        - NEVER: system state, health, history, recommendations, logs, insights
        - NEVER: task planning, code, files, project management
        - NEVER: raw Pulse data, WorkUnit IDs, model names, costs, tokens
        - NEVER: internal structures, module names (P6 — functional labels only)
        - suggested_action is always None (pure query, no action)
        """
        # ── Validate parameters ──────────────────────────────────────────
        if periodo is not None and periodo not in _PROGRESS_PERIODOS:
            return self._build_error_response(
                "ERR_INVALID_ARGUMENT",
                "periodo debe ser uno de: None, 'hoy', 'semana', 'mes'",
            )

        # ── Pulse is required — no degraded mode ─────────────────────────
        if self._services.pulse is None:
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                "No se pudo consultar los datos de productividad",
            )

        # ── Build WorkUnitFilter from periodo ────────────────────────────
        from apoch.modules.pulse.models import WorkUnitFilter

        now = datetime.now(UTC)
        if periodo is None:
            since = (now - timedelta(hours=24)).isoformat()
        elif periodo == "hoy":
            since = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        else:
            days = _PROGRESS_DAYS.get(periodo, 1)
            since = (now - timedelta(days=days)).isoformat()

        wf = WorkUnitFilter(since=since, limit=1000)
        pulse_timeout = self._timeouts.get("pulse", 0.5)

        # ── Build parallel queries: list + trend ─────────────────────────
        queries: list[tuple[str, Any, float]] = []

        if hasattr(self._services.pulse, "list"):
            pulse_list_fn = self._services.pulse.list

            async def _fetch_pulse_list() -> Any:
                result = pulse_list_fn(wf)
                if asyncio.iscoroutine(result):
                    return await result
                return result

            queries.append(("pulse_list", _fetch_pulse_list(), pulse_timeout))

        if hasattr(self._services.pulse, "trend"):
            trend_window = _PROGRESS_TREND_WINDOW.get(periodo or "hoy", 1)
            pulse_trend_fn = self._services.pulse.trend

            async def _fetch_pulse_trend() -> Any:
                result = pulse_trend_fn(trend_window)
                if asyncio.iscoroutine(result):
                    return await result
                return result

            queries.append(("pulse_trend", _fetch_pulse_trend(), pulse_timeout))

        results = await self._query_modules(queries)
        pulse_list = results.get("pulse_list")
        pulse_trend = results.get("pulse_trend")

        # ── Handle unavailable Pulse (timeout / exception / None) ────────
        if pulse_list is None:
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                "No se pudo consultar los datos de productividad",
            )

        # ── Handle no data (Pulse responded but empty) ───────────────────
        if not pulse_list:
            evidence = [
                EvidenceSource(
                    source="Sistema de rendimiento",
                    confidence=0.3,
                    collected_ago=0,
                    based_on="0 unidades de trabajo",
                ),
            ]
            return {
                "api_version": API_VERSION,
                "summary": "No hay datos de actividad para el período solicitado.",
                "explanation": ("No hay datos de actividad en el período seleccionado."),
                "evidence": [e.to_dict() for e in evidence],
                "suggested_action": None,
                "confidence": 0.3,
                "generated_at": now.isoformat(),
                "data_freshness": 0,
                "metadata": {},
            }

        # ── Interpret trends from Pulse data ─────────────────────────────
        total_count = len(pulse_list)
        trend_points = pulse_trend if isinstance(pulse_trend, list) else []
        trend_label, trend_desc = self._interpret_progress_trend(
            total_count,
            trend_points,
        )

        # ── Build summary ───────────────────────────────────────────────
        if trend_label == "baja":
            summary = "Actividad baja"
        elif trend_label in ("creciente", "decreciente", "estable"):
            summary = f"Productividad {trend_label}"
        else:
            summary = "Actividad registrada"

        # ── Build explanation ────────────────────────────────────────────
        explanation_parts: list[str] = [
            f"Se registraron {total_count} unidades de trabajo en el período solicitado.",
        ]
        if trend_desc:
            explanation_parts.append(trend_desc)
        explanation = " ".join(explanation_parts)

        # ── Confidence derived from available data and trend ─────────────
        if len(trend_points) >= 2:
            confidence = 0.7
        else:
            confidence = 0.5

        # ── Build evidence with functional labels (P6 compliance) ────────
        based_on = f"{total_count} unidades de trabajo"
        evidence = [
            EvidenceSource(
                source="Sistema de rendimiento",
                confidence=0.8,
                collected_ago=0,
                based_on=based_on,
            ),
        ]

        # ── Build response ──────────────────────────────────────────────
        now_ts = datetime.now(UTC)
        return {
            "api_version": API_VERSION,
            "summary": summary,
            "explanation": explanation,
            "evidence": [e.to_dict() for e in evidence],
            "suggested_action": None,
            "confidence": confidence,
            "generated_at": now_ts.isoformat(),
            "data_freshness": 0,
            "metadata": {},
        }

    # ── Legacy alias wrappers (PR9 — backward compatibility) ──────────
    #
    # Each wrapper accepts legacy parameter names, delegates to the
    # corresponding public tool, and injects deprecation metadata.

    async def legacy_vision_state(
        self,
        module: str | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """[DEPRECATED] Use apoch_status instead.

        Legacy alias that delegates to :meth:`status`.
        """
        result = await self.status()
        result["metadata"] = {
            "legacy_tool": "vision_state",
            "replaced_by": "apoch_status",
            "deprecated_since": "1.0",
        }
        return result

    async def legacy_chronicle_query(
        self,
        source: str | None = None,  # noqa: ARG002
        event_type: str | None = None,
        since: str | None = None,
        until: str | None = None,  # noqa: ARG002
        limit: int | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """[DEPRECATED] Use apoch_history instead.

        Legacy alias that delegates to :meth:`history`. Maps ``event_type``
        and ``since`` to the public ``tipo``/``horas`` params when provided.
        """
        horas: int | None = None
        tipo: str | None = None

        if since is not None:
            try:
                from datetime import datetime as _dt  # noqa: PLC0415

                since_dt = _dt.fromisoformat(since)
                if since_dt.tzinfo is None:
                    from datetime import UTC as _UTC  # noqa: PLC0415

                    since_dt = since_dt.replace(tzinfo=_UTC)
                delta = datetime.now(UTC) - since_dt
                horas = max(1, int(delta.total_seconds() // 3600))
            except (ValueError, TypeError):
                horas = None

        if event_type is not None:
            _et_map: dict[str, str] = {
                "tool_call": "tool",
                "error": "error",
                "lifecycle": "lifecycle",
                "state_change": "lifecycle",
            }
            tipo = _et_map.get(event_type)

        result = await self.history(horas=horas, tipo=tipo)
        result["metadata"] = {
            "legacy_tool": "chronicle_query",
            "replaced_by": "apoch_history",
            "deprecated_since": "1.0",
        }
        return result

    async def legacy_guardian_diagnostics(
        self,
        module_name: str,  # noqa: ARG002
    ) -> dict[str, Any]:
        """[DEPRECATED] Use apoch_health instead.

        Legacy alias that delegates to :meth:`health`.
        """
        result = await self.health()
        result["metadata"] = {
            "legacy_tool": "guardian_diagnostics",
            "replaced_by": "apoch_health",
            "deprecated_since": "1.0",
        }
        return result

    async def legacy_guardian_all_diagnostics(self) -> dict[str, Any]:
        """[DEPRECATED] Use apoch_health instead.

        Legacy alias that delegates to :meth:`health`.
        """
        result = await self.health()
        result["metadata"] = {
            "legacy_tool": "guardian_all_diagnostics",
            "replaced_by": "apoch_health",
            "deprecated_since": "1.0",
        }
        return result

    async def legacy_vision_logs(
        self,
        limit: int | None = 50,
        level: str | None = None,
    ) -> dict[str, Any]:
        """[DEPRECATED] Use apoch_logs instead.

        Legacy alias that delegates to :meth:`logs`. Maps ``limit`` to
        ``limite`` and ``level`` to ``nivel``.
        """
        result = await self.logs(limite=limit, nivel=level)
        result["metadata"] = {
            "legacy_tool": "vision_logs",
            "replaced_by": "apoch_logs",
            "deprecated_since": "1.0",
        }
        return result

    @staticmethod
    def _interpret_progress_trend(
        total_count: int,
        trend_points: list[Any],
    ) -> tuple[str, str]:
        """Interpret productivity trend from total count and TrendPoints.

        Returns ``(label, description)`` where *label* is one of:
        ``"creciente"``, ``"decreciente"``, ``"estable"``, ``"baja"``.

        *description* is a human-readable sentence or empty string.
        """
        if total_count == 0:
            return "", ""

        if total_count < _PROGRESS_LOW_THRESHOLD:
            return "baja", (
                f"La actividad registrada es baja "
                f"({total_count} unidades de trabajo en el período solicitado)."
            )

        if len(trend_points) >= 2:
            recent = trend_points[-1]
            previous = trend_points[-2]

            if recent.work_unit_count > previous.work_unit_count:
                return "creciente", (
                    "La actividad está aumentando en comparación con el período anterior."
                )
            if recent.work_unit_count < previous.work_unit_count:
                return "decreciente", (
                    "La actividad está disminuyendo en comparación con el período anterior."
                )
            return "estable", ("La actividad se mantiene estable respecto al período anterior.")

        # Data available but only one trend point — no comparison possible
        return "estable", ("Actividad registrada sin cambios significativos.")

    @_auto_emit_tool_events
    async def insights(self) -> dict[str, Any]:
        """Patterns and improvement opportunities.

        Spec: mcp-public-api §Tool 6: apoch_insights
        Design: ADR-001, ADR-004, ADR-007

        Boundaries:
        - Optimizer is REQUIRED (ERR_DEPENDENCY_UNAVAILABLE if absent).
        - Pulse is OPTIONAL (degraded confidence if absent/times out).
        - Only exposes hypotheses with type=pattern (deterministic filter).
        - Never serializes OptimizationHypothesis.evidence dict.
        - Never exposes module names, detector names, or internal stats.
        - suggested_action is always None.
        """
        queries: list[tuple[str, Any, float]] = []
        pulse_factor: float = 1.0
        opt_queried = False

        # ── Optimizer (required) ────────────────────────────────────────
        if self._services.optimizer is not None and hasattr(self._services.optimizer, "services"):
            opt_svc = self._services.optimizer.services.get("optimizer.hypotheses")
            if opt_svc:
                opt_queried = True

                async def _fetch_opt_hypotheses() -> Any:
                    result = opt_svc()
                    if asyncio.iscoroutine(result):
                        return await result
                    return result

                queries.append(
                    (
                        "optimizer",
                        _fetch_opt_hypotheses(),
                        self._timeouts.get("optimizer", 1.0),
                    )
                )

        if not opt_queried:
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                "No se pudo consultar el optimizador del sistema",
            )

        # ── Pulse (optional) ────────────────────────────────────────────
        if self._services.pulse is not None and hasattr(self._services.pulse, "list"):
            pulse_list_fn = self._services.pulse.list

            async def _fetch_pulse_data() -> Any:
                result = pulse_list_fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result

            queries.append(
                (
                    "pulse",
                    _fetch_pulse_data(),
                    self._timeouts.get("pulse", 0.5),
                )
            )
        else:
            pulse_factor = 0.5

        results = await self._query_modules(queries)
        optimizer_data = results.get("optimizer")

        # ── Optimizer failed / timed out ────────────────────────────────
        if optimizer_data is None:
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                "No se pudo consultar el optimizador del sistema",
            )

        # ── Determine pulse factor after query ──────────────────────────
        pulse_data = results.get("pulse")
        if pulse_data is None and pulse_factor == 1.0:
            pulse_factor = 0.7

        # ── Filter: only type=pattern (deterministic) ───────────────────
        filtered = [h for h in optimizer_data if getattr(h, "type", None) == "pattern"]

        # ── No patterns → friendly response, not error ──────────────────
        if not filtered:
            now = datetime.now(UTC)
            evidence_entry = EvidenceSource(
                source="Sistema de optimización",
                confidence=0.8,
                collected_ago=0,
                based_on="sin patrones detectados",
            )
            return {
                "api_version": API_VERSION,
                "summary": "No se detectaron patrones ni oportunidades de mejora.",
                "explanation": "No se detectaron patrones ni oportunidades de mejora.",
                "evidence": [evidence_entry.to_dict()],
                "suggested_action": None,
                "confidence": 0.0,
                "generated_at": now.isoformat(),
                "data_freshness": 0,
                "metadata": {},
            }

        # ── Confidence formula ──────────────────────────────────────────
        hypothesis_avg = sum(h.confidence for h in filtered) / len(filtered)
        confidence = round(hypothesis_avg * pulse_factor, 2)

        # ── Natural language translation (P6 — no internal exposure) ────
        domain_labels: dict[str, str] = {
            "cost": "costos",
            "time": "tiempo de trabajo",
            "rework": "reproceso",
            "model_efficiency": "eficiencia del modelo",
            "session_behavior": "comportamiento de sesión",
        }

        lines: list[str] = []
        for h in filtered:
            domain_text = domain_labels.get(h.domain, str(h.domain))
            lines.append(
                f"Detecté un patrón en {h.affected_scope} "
                f"que puede estar afectando tu {domain_text}.",
            )
        explanation = "\n".join(lines)

        n = len(filtered)
        summary = f"Se detectaron {n} patrones de productividad"

        # ── Evidence with functional labels (P6 compliance) ──────────────
        evidence_sources: list[EvidenceSource] = [
            EvidenceSource(
                source="Sistema de optimización",
                confidence=0.8,
                collected_ago=0,
                based_on=f"{n} patrón(es) detectado(s)",
            ),
        ]
        if pulse_data is not None:
            n_units = len(pulse_data) if isinstance(pulse_data, list) else 0
            evidence_sources.append(
                EvidenceSource(
                    source="Sistema de rendimiento",
                    confidence=0.7,
                    collected_ago=0,
                    based_on=(
                        f"{n_units} unidades de trabajo" if n_units else "datos de rendimiento"
                    ),
                ),
            )

        now = datetime.now(UTC)
        return {
            "api_version": API_VERSION,
            "summary": summary,
            "explanation": explanation,
            "evidence": [e.to_dict() for e in evidence_sources],
            "suggested_action": None,
            "confidence": confidence,
            "generated_at": now.isoformat(),
            "data_freshness": 0,
            "metadata": {},
        }

    @_auto_emit_tool_events
    async def logs(
        self,
        nivel: str | None = None,
        limite: int | None = LOGS_DEFAULT_LIMIT,
        modulo: str | None = None,
    ) -> dict[str, Any]:
        """Technical logs for debugging.

        Spec: mcp-public-api §Tool 7: apoch_logs
        Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

        Boundaries (see spec §1.4, §1.9):
        - Single module dependency: Vision is REQUIRED
        - NEVER: context, pid, LogRecord objects, internal structures (P6)
        - NEVER: historical narrative (belongs to apoch_history)
        - suggested_action is always None (pure query)
        - Filter by module is applied in memory (Vision.recent() does not support it)
        - When modulo + limite are used together, limite applies AFTER module filter
        """
        # ── Validate parameters ──────────────────────────────────────────
        resolved_limit: int = limite if limite is not None else LOGS_DEFAULT_LIMIT
        if not isinstance(resolved_limit, int) or resolved_limit <= 0:
            return self._build_error_response(
                "ERR_INVALID_ARGUMENT",
                "limite debe ser un entero positivo",
            )

        if nivel is not None and nivel.upper() not in _LOGS_VALID_LEVELS:
            return self._build_error_response(
                "ERR_INVALID_ARGUMENT",
                "nivel debe ser uno de: INFO, WARN, ERROR, FATAL",
            )

        # ── Vision is required — no degraded mode ────────────────────────
        if self._services.vision is None or not hasattr(self._services.vision, "recent"):
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                "No se pudo consultar los logs del sistema",
            )

        # ── Query Vision ─────────────────────────────────────────────────
        queries: list[tuple[str, Any, float]] = [
            (
                "vision",
                self._services.vision.recent(
                    limit=resolved_limit,
                    level=nivel,
                ),
                self._timeouts.get("vision", LOGS_VISION_TIMEOUT),
            ),
        ]

        results = await self._query_modules(queries)
        vision_data = results.get("vision")

        # ── Handle unavailable Vision (timeout / exception / None) ───────
        if vision_data is None:
            return self._build_error_response(
                "ERR_DEPENDENCY_UNAVAILABLE",
                "No se pudo consultar los logs del sistema",
            )

        # ── Apply module filter in memory (Vision.recent() does not support it) ─
        if modulo is not None and vision_data:
            filtered = [r for r in vision_data if getattr(r, "module", None) == modulo]
            # When modulo + limite are used, limite applies AFTER module filter
            filtered = filtered[:resolved_limit]
            entries = filtered
        else:
            entries = vision_data  # Already limited by Vision.recent()

        # ── Format entries (P6: only timestamp, level, message, module) ──
        if not entries:
            summary = "No hay entradas de log que coincidan con los filtros especificados."
            explanation = summary
            confidence = 0.3
            based_on = "0 entradas"
        else:
            lines: list[str] = []
            for entry in entries:
                ts = entry.timestamp.isoformat() if hasattr(entry, "timestamp") else ""
                level = getattr(entry, "level", "UNKNOWN")
                msg = getattr(entry, "message", "")
                mod = getattr(entry, "module", None)
                if mod:
                    lines.append(f"[{ts}] {level} [{mod}] — {msg}")
                else:
                    lines.append(f"[{ts}] {level} — {msg}")
            explanation = "\n".join(lines)
            summary = f"Se encontraron {len(entries)} entradas de log"
            confidence = 1.0
            based_on = f"{len(entries)} entradas"

        # ── Build evidence with functional labels (P6) ───────────────────
        evidence_entry = EvidenceSource(
            source="Sistema de monitoreo",
            confidence=0.8,
            collected_ago=0,
            based_on=based_on,
        )

        # ── Build response ──────────────────────────────────────────────
        now = datetime.now(UTC)
        return {
            "api_version": API_VERSION,
            "summary": summary,
            "explanation": explanation,
            "evidence": [evidence_entry.to_dict()],
            "suggested_action": None,
            "confidence": confidence,
            "generated_at": now.isoformat(),
            "data_freshness": 0,
            "metadata": {},
        }
