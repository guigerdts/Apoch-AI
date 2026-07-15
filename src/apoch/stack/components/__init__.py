"""Stack component implementations.

Every component registers via the ``apoch.stack.components`` entry-point
group in ``pyproject.toml`` — zero changes to :class:`StackManager`.
"""

from apoch.stack.components.openspec import DESCRIPTOR, OpenSpecComponent

__all__ = [
    "DESCRIPTOR",
    "OpenSpecComponent",
]
