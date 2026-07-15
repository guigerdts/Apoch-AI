"""Core Stack — installation and lifecycle management for platform components.

Spec: core-stack
Design: Core Stack Installation & Lifecycle
PROJECT_MASTER.md §8 — Core Stack

This package implements the Stack layer (CLI → Stack → Integrations).
It is independent from ``apoch/core/`` — Rule 005.
"""

from __future__ import annotations

from apoch.stack.clock import ClockProvider, FakeClock, RealClock
from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.downloader import Downloader, MockDownloader, RealDownloader
from apoch.stack.exceptions import (
    StackError,
    StackInstallError,
    StackLockError,
    StackManifestError,
    StackNotFoundError,
    StackStateError,
    StackUninstallError,
    StackVerifyError,
)
from apoch.stack.factory import create_manager
from apoch.stack.lock import FileLock
from apoch.stack.manager import ComponentStatus, StackManager
from apoch.stack.manifest import StackManifest, StackManifestEntry
from apoch.stack.paths import StackPaths
from apoch.stack.registry import StackRegistry
from apoch.stack.result import OperationResult
from apoch.stack.runner import CommandRunner, MockRunner, RealRunner, RunResult
from apoch.stack.state import StackState

__all__ = [
    "ClockProvider",
    "CommandRunner",
    "ComponentInfo",
    "ComponentStatus",
    "create_manager",
    "Downloader",
    "FakeClock",
    "FileLock",
    "MockDownloader",
    "MockRunner",
    "OperationResult",
    "RealClock",
    "RealDownloader",
    "RealRunner",
    "RunResult",
    "StackComponent",
    "StackDescriptor",
    "StackError",
    "StackInstallError",
    "StackLockError",
    "StackManifest",
    "StackManifestError",
    "StackManifestEntry",
    "StackManager",
    "StackNotFoundError",
    "StackPaths",
    "StackRegistry",
    "StackState",
    "StackStateError",
    "StackUninstallError",
    "StackVerifyError",
]
