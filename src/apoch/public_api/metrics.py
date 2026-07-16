"""Internal metrics for the Apoch Coordinator.

``CallMetrics`` records per-invocation performance data for monitoring
and diagnostics. These are NOT exposed via MCP — they are stored
internally (e.g. in Chronicle) for dashboard and debugging purposes.

Design: ADR-Metrics (§Métricas Internas del Coordinador)
"""

from dataclasses import dataclass


@dataclass
class CallMetrics:
    """Per-call performance and reliability metrics.

    Recorded after every public tool invocation to track degradation,
    timeouts, and confidence trends across modules.

    Attributes:
        tool: Tool name (e.g. ``"apoch_status"``).
        modules_consulted: Modules that were queried for this call.
        modules_succeeded: Modules that responded within timeout.
        modules_failed: Modules that timed out or raised errors.
        time_per_module: Seconds spent waiting for each module.
        total_time: Total wall-clock time for this call in seconds.
        confidence_final: Resulting confidence level (0.00–1.00).
        evidence_count: Number of evidence sources in the response.
        timestamp: ISO 8601 timestamp of when the call completed.
        error_code: Error code if the call failed, or None.
    """

    tool: str
    modules_consulted: list[str]
    modules_succeeded: list[str]
    modules_failed: list[str]
    time_per_module: dict[str, float]
    total_time: float
    confidence_final: float
    evidence_count: int
    timestamp: str
    error_code: str | None = None
