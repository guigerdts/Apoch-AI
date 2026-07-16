"""Service registry for the Apoch Coordinator.

Provides a typed container for all internal modules that the public API
layer may consult. Each field is Optional — None means the module is
not loaded and is treated as unavailable.

Design: ADR-001 (ServiceRegistry dataclass)
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceRegistry:
    """Typed container for Apoch internal services.

    The ``ApochCoordinator`` receives a ``ServiceRegistry`` with the
    modules that were loaded during startup. Unloaded modules are
    ``None`` and treated as unavailable.

    Attributes:
        vision: Vision module (system state, logs) or None.
        chronicle: Chronicle module (events, history) or None.
        guardian: Guardian module (diagnostics, health) or None.
        pulse: Pulse module (measurements, analysis) or None.
        optimizer: Optimizer module (hypotheses, patterns) or None.
        oracle: Oracle module (recommendations, predictions) or None.
    """

    vision: Any = None
    chronicle: Any = None
    guardian: Any = None
    pulse: Any = None
    optimizer: Any = None
    oracle: Any = None
