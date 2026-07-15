"""Stack component implementations.

Every component registers via the ``apoch.stack.components`` entry-point
group in ``pyproject.toml`` — zero changes to :class:`StackManager`.
"""

from apoch.stack.components.context7 import CONTEXT7_DESCRIPTOR, Context7Component
from apoch.stack.components.engram import ENGRA_DESCRIPTOR, EngramComponent
from apoch.stack.components.openspec import DESCRIPTOR, OpenSpecComponent

__all__ = [
    "CONTEXT7_DESCRIPTOR",
    "Context7Component",
    "DESCRIPTOR",
    "ENGRA_DESCRIPTOR",
    "EngramComponent",
    "OpenSpecComponent",
]
