"""Domain models for the Oracle recommendation engine.

Spec: oracle-recommendation-engine §R4, R9, R11
Design: Oracle — Recommendation Engine §Data Model
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

RecommendationPriority = Literal["critical", "high", "medium", "low"]
RecommendationDomain = Literal[
    "cost",
    "time",
    "rework",
    "model_efficiency",
    "session_behavior",
    "general",
]
RecommendationStatus = Literal["active", "accepted", "rejected", "expired"]


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Recommendation:
    """An actionable recommendation derived from optimization hypotheses.

    Immutable after creation (R10). All analysis is read-only.

    Attributes:
        id: Unique identifier (UUID hex string).
        title: Human-readable short title.
        description: Detailed description of the recommendation.
        priority: Urgency level (critical > high > medium > low).
        confidence: Confidence score in range 0.0–1.0.
        evidence: Supporting data dict from source hypothesis + health notes.
        justification: Why this recommendation was made.
        dependencies: Module service dependencies required to act on this rec.
        expiration: ISO 8601 timestamp when this recommendation expires.
        source_hypotheses: IDs of source OptimizationHypothesis instances.
        domain: Domain this recommendation applies to.
        status: Current lifecycle status (active/accepted/rejected/expired).
        created_at: ISO 8601 timestamp of creation.
    """

    id: str
    title: str
    description: str
    priority: RecommendationPriority
    confidence: float
    evidence: dict
    justification: str
    dependencies: list[str]
    expiration: str
    source_hypotheses: list[str]
    domain: RecommendationDomain
    status: RecommendationStatus
    created_at: str


__all__ = [
    "Recommendation",
    "RecommendationDomain",
    "RecommendationPriority",
    "RecommendationStatus",
]
