"""Domain model for Optimizer's engineering optimization intelligence.

Spec: optimizer-engineering-optimization §R7, R8
Design: Optimizer — Engineering Optimization Intelligence §Data Model
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class OptimizationHypothesis:
    """A detected pattern, anomaly, or opportunity for optimization.

    Immutable after creation — all analysis is read-only (R10).

    Attributes:
        type: Classification of the finding.
        domain: Domain the hypothesis applies to.
        confidence: Statistical or heuristic confidence (0.0–1.0).
        evidence: Detector-specific supporting data.
        affected_scope: Human-readable scope description.
        generated_at: ISO 8601 timestamp of hypothesis generation.
    """

    type: Literal["pattern", "anomaly", "opportunity"]
    domain: Literal["cost", "time", "rework", "model_efficiency", "session_behavior"]
    confidence: float
    evidence: dict
    affected_scope: str
    generated_at: str


__all__ = [
    "OptimizationHypothesis",
]
