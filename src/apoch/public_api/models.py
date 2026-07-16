"""Data models for the public MCP API.

Defines the unified response contract (ToolResponse), evidence model,
error envelope, and specialized subclasses used by all public MCP tools.

Design: ADR-002 (ToolResponse contract), ADR-003 (EvidenceSource)
Spec: mcp-public-api §ToolResponse format, §EvidenceSource
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceSource:
    """A single source of evidence backing a ToolResponse.

    Each module consulted during tool execution contributes one
    EvidenceSource describing what data was provided, when it was
    collected, and how reliable it is.

    Attributes:
        source: Module name that provided this evidence ("Vision", "Guardian", etc.).
        confidence: Reliability of this source (0.00–1.00).
        collected_ago: Seconds since the data was collected.
        based_on: Human-readable description of the basis (e.g. "38 work units").
    """

    source: str
    confidence: float
    collected_ago: int
    based_on: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "source": self.source,
            "confidence": self.confidence,
            "collected_ago": self.collected_ago,
            "based_on": self.based_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceSource":
        """Deserialize from a dict (ignores extra keys)."""
        return cls(
            source=data["source"],
            confidence=data["confidence"],
            collected_ago=data["collected_ago"],
            based_on=data["based_on"],
        )


@dataclass
class ToolResponse:
    """Unified response contract for all public MCP tools.

    Every tool returns this structure serialized as a dict inside the
    standard MCP envelope (``{"version": 1, "ok": true, "data": {...}}``).

    Attributes:
        api_version: Version of the API contract (always "1.0" initially).
        summary: One-line summary of the answer.
        explanation: Brief context for the answer.
        evidence: List of sources that back the answer.
        suggested_action: Recommended next action, or None.
        confidence: Global confidence level (0.00–1.00).
        generated_at: ISO 8601 timestamp of when the response was built.
        data_freshness: Age of the source data in seconds.
        metadata: Reserved for extensibility (legacy compat, future fields).
    """

    api_version: str = "1.0"
    summary: str = ""
    explanation: str = ""
    evidence: list[EvidenceSource] = field(default_factory=list)
    suggested_action: str | None = None
    confidence: float = 0.0
    generated_at: str = ""
    data_freshness: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict.

        Evidence sources are serialized recursively. The ``api_version``
        field is always first for client-side detection (see ADR-005).
        """
        return {
            "api_version": self.api_version,
            "summary": self.summary,
            "explanation": self.explanation,
            "evidence": [e.to_dict() for e in self.evidence],
            "suggested_action": self.suggested_action,
            "confidence": self.confidence,
            "generated_at": self.generated_at,
            "data_freshness": self.data_freshness,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolResponse":
        """Deserialize from a dict (ignores extra keys).

        Evidence entries are deserialized back into ``EvidenceSource`` objects.
        """
        evidence = [EvidenceSource.from_dict(e) for e in data.get("evidence", [])]
        return cls(
            api_version=data.get("api_version", "1.0"),
            summary=data["summary"],
            explanation=data["explanation"],
            evidence=evidence,
            suggested_action=data.get("suggested_action"),
            confidence=data.get("confidence", 0.0),
            generated_at=data.get("generated_at", ""),
            data_freshness=data.get("data_freshness", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RecommendResponse(ToolResponse):
    """Extended response for ``apoch_recommend`` with priority information.

    Adds recommendation-specific fields on top of the standard ToolResponse.

    Attributes:
        priority: Urgency of the recommendation (HIGH, MEDIUM, LOW).
        expected_benefit: Projected positive impact, or None.
    """

    priority: str = "MEDIUM"
    expected_benefit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize including recommendation-specific fields."""
        base = super().to_dict()
        base["priority"] = self.priority
        base["expected_benefit"] = self.expected_benefit
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecommendResponse":
        """Deserialize from a dict with recommendation fields."""
        evidence = [EvidenceSource.from_dict(e) for e in data.get("evidence", [])]
        return cls(
            api_version=data.get("api_version", "1.0"),
            summary=data["summary"],
            explanation=data["explanation"],
            evidence=evidence,
            suggested_action=data.get("suggested_action"),
            confidence=data.get("confidence", 0.0),
            generated_at=data.get("generated_at", ""),
            data_freshness=data.get("data_freshness", 0),
            metadata=data.get("metadata", {}),
            priority=data.get("priority", "MEDIUM"),
            expected_benefit=data.get("expected_benefit"),
        )


@dataclass
class ErrorResponse:
    """Error envelope returned when a tool cannot produce a valid response.

    Follows the format defined in the error catalog:
    ``{"ok": false, "error": {"code": "...", "message": "..."}}``

    Attributes:
        ok: Always False for error responses.
        error: Dict with ``code`` and ``message`` keys.
    """

    ok: bool = False
    error: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {"ok": self.ok, "error": self.error}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorResponse":
        """Deserialize from a dict."""
        return cls(ok=data.get("ok", False), error=data.get("error", {}))
