"""Shared confidence helpers for Optimizer detectors.

Spec: optimizer-engineering-optimization §R8
Design: Optimizer — Engineering Optimization Intelligence §Confidence Scoring
"""

from __future__ import annotations


def cap_underpowered(score: float, n: int) -> float:
    """Cap confidence when the sample size is statistically underpowered.

    If fewer than 3 data points are available, the confidence is capped
    at 0.5 to reflect lower certainty.  The result is always clamped to
    the [0.0, 1.0] range.

    This is a deterministic pure function — same inputs always produce
    the same output.

    Args:
        score: Raw confidence score.
        n: Number of data points the score is based on.

    Returns:
        Capped and clamped confidence value in [0.0, 1.0].
    """
    if n < 3:
        score = min(score, 0.5)
    return max(0.0, min(1.0, score))


__all__ = [
    "cap_underpowered",
]
