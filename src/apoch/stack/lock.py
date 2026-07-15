"""File-based lock with stale detection for stack operations.

Ensures mutual exclusion during installation, uninstallation, and other
state-changing stack operations.

Design: Core Stack Installation & Lifecycle — FileLock
"""

from __future__ import annotations

import errno
import os
import time
from pathlib import Path
from types import TracebackType

from apoch.stack.exceptions import StackLockError


class FileLock:
    """A file-based mutual exclusion lock.

    The lock uses an atomic ``O_CREAT | O_EXCL`` file creation at *path*
    with the current PID as content.

    Args:
        path:            Filesystem path for the lock file.
        stale_threshold: Seconds after which an existing lock file is
                         considered stale and can be broken.
    """

    def __init__(self, path: Path, stale_threshold: int = 300) -> None:
        self.path = path
        self._stale_threshold = stale_threshold
        self._fd: int | None = None

    # ── Public API ───────────────────────────────────────────────────

    def acquire(self, timeout: float = -1) -> bool:
        """Acquire the lock.

        Args:
            timeout: Maximum seconds to wait. Negative means no timeout
                     (fail immediately), zero means infinite wait.

        Returns:
            ``True`` if the lock was acquired.

        Raises:
            StackLockError: If the lock cannot be acquired within
                            *timeout*.
        """
        deadline = (
            float("inf") if timeout == 0 else (time.monotonic() + timeout) if timeout > 0 else 0
        )

        while True:
            self._try_break_stale()
            try:
                self._fd = os.open(
                    str(self.path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
                os.write(self._fd, str(os.getpid()).encode())
                return True
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    msg = f"Cannot acquire lock at {self.path}: {exc}"
                    raise StackLockError(msg) from exc

                if time.monotonic() >= deadline:
                    msg = f"Cannot acquire lock at {self.path} — already held by another process"
                    raise StackLockError(msg)

                time.sleep(0.1)

    def release(self) -> None:
        """Release the lock.

        Raises:
            StackLockError: If the lock is not currently held.
        """
        if self._fd is None:
            msg = f"Lock at {self.path} is not held"
            raise StackLockError(msg)

        os.close(self._fd)
        self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass  # Already removed — that's OK

    def locked(self) -> bool:
        """Return ``True`` if the lock file exists on disk."""
        return self.path.exists()

    # ── Context manager ──────────────────────────────────────────────

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        if self._fd is not None:
            self.release()

    def __str__(self) -> str:
        status = "locked" if self._fd is not None else "unlocked"
        return f"FileLock({self.path}, {status})"

    # ── Internal helpers ─────────────────────────────────────────────

    def _try_break_stale(self) -> None:
        """Remove the lock file if it is older than the stale threshold."""
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            return

        age = time.time() - mtime
        if age >= self._stale_threshold:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
