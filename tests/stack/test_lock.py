"""Tests for FileLock — file-based locking with stale detection.

Design: Core Stack Installation & Lifecycle — FileLock
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from apoch.stack.exceptions import StackLockError
from apoch.stack.lock import FileLock


class TestFileLock:
    """Verify file-based locking behaviour."""

    @pytest.fixture
    def lock_path(self, tmp_path: Path) -> Path:
        return tmp_path / "stack.lock"

    @pytest.fixture
    def lock(self, lock_path: Path) -> FileLock:
        return FileLock(lock_path)

    def test_initial_state_is_unlocked(self, lock: FileLock):
        """A fresh lock is not acquired."""
        assert lock.locked() is False

    def test_acquire_and_release(self, lock: FileLock):
        """Acquire then release works."""
        lock.acquire()
        assert lock.locked() is True
        lock.release()
        assert lock.locked() is False

    def test_acquire_twice_blocks(self, lock: FileLock):
        """Acquiring an already-held lock raises StackLockError."""
        lock.acquire()
        with pytest.raises(StackLockError):
            lock.acquire(timeout=0.1)
        lock.release()

    def test_release_unlocked_lock(self, lock: FileLock):
        """Releasing a lock that is not held raises StackLockError."""
        with pytest.raises(StackLockError):
            lock.release()

    def test_lock_file_is_created(self, lock: FileLock, lock_path: Path):
        """Acquiring the lock creates a lock file on disk."""
        lock.acquire()
        assert lock_path.exists()
        lock.release()

    def test_lock_file_is_removed_on_release(self, lock: FileLock, lock_path: Path):
        """Releasing the lock removes the lock file."""
        lock.acquire()
        lock.release()
        assert not lock_path.exists()

    def test_context_manager(self, lock: FileLock):
        """FileLock works as a context manager."""
        with lock:
            assert lock.locked() is True
        assert lock.locked() is False

    def test_context_manager_raises_on_existing_lock(self, lock: FileLock):
        """Context manager raises StackLockError if already locked."""
        lock.acquire()
        with pytest.raises(StackLockError):
            with lock:
                pass  # noqa: SIM117
        lock.release()

    def test_stale_lock_is_removed(self, lock_path: Path):
        """A lock file older than stale_threshold is automatically broken."""
        # Create an old lock file
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(str(os.getpid()))

        # Set its mtime to be very old
        old_time = time.time() - 3600  # 1 hour ago
        os.utime(lock_path, (old_time, old_time))

        lock = FileLock(lock_path, stale_threshold=300)  # 5 min stale
        lock.acquire()
        assert lock.locked() is True

    def test_non_stale_lock_is_not_broken(self, lock_path: Path, lock: FileLock):
        """A recent lock file is NOT automatically broken."""
        lock.acquire()

        lock2 = FileLock(lock_path, stale_threshold=300)
        with pytest.raises(StackLockError):
            lock2.acquire(timeout=0.1)

        lock.release()

    def test_str_representation(self, lock: FileLock):
        """__str__ shows the lock path and state."""
        s = str(lock)
        assert "lock" in s.lower()
        assert str(lock.path) in s
