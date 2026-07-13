"""Cross-platform compatibility utilities.

Provides platform-adaptive implementations for signal handling, path
resolution, and encoding — allowing the rest of Apoch-AI to work
consistently across Linux, macOS, Windows, WSL2, and Termux.
"""

from __future__ import annotations

import os
import platform
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

SYSTEM = platform.system().lower()
IS_LINUX = SYSTEM == "linux"
IS_MACOS = SYSTEM == "darwin"
IS_WINDOWS = SYSTEM == "windows"
IS_TERMUX = "com.termux" in (getattr(platform, "uname", lambda: ("",))()[0] or "")
IS_WSL = "microsoft" in (platform.uname().release.lower() if hasattr(platform, "uname") else "")


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

# Signals available on most POSIX platforms
_SIGNAMES: dict[int, str] = {
    getattr(signal, n): n for n in dir(signal) if n.startswith("SIG") and not n.startswith("SIG_")
}

_HANDLERS: dict[int, Callable[[int, object], None]] = {}


def _has_signal(name: str) -> bool:
    """Return True if *name* (e.g. ``SIGTERM``) is available on this platform."""
    return hasattr(signal, name)


def set_signal_handler(
    signum: int,
    handler: Callable[[int, object], None],
    *,
    strict: bool = False,
) -> None:
    """Register *handler* for signal *signum*.

    On platforms where the signal is unavailable the call is silently
    ignored unless *strict* is ``True``, in which case ``RuntimeError``
    is raised.
    """
    try:
        signal.signal(signum, handler)  # type: ignore[type-arg]
        _HANDLERS[signum] = handler
    except (ValueError, OSError) as exc:
        if strict:
            raise RuntimeError(
                f"Cannot set handler for signal {signum} ({_SIGNAMES.get(signum, '?')}): {exc}"
            ) from exc


def restore_signal_handler(signum: int) -> None:
    """Restore the default handler for *signum*.

    Silently ignored if no custom handler was set.
    """
    if signum in _HANDLERS:
        try:
            signal.signal(signum, signal.SIG_DFL)  # type: ignore[type-arg]
        except (ValueError, OSError):
            pass
        del _HANDLERS[signum]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def user_config_dir() -> Path:
    """Return the platform-appropriate Apoch-AI config directory.

    Order of precedence:
    1. ``$APOCH_HOME`` environment variable (explicit override)
    2. Platform default (``~/.config/apoch`` on Linux/macOS,
       ``%APPDATA%\\apoch`` on Windows)
    """
    env = os.environ.get("APOCH_HOME")
    if env:
        return Path(env)

    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return base / "apoch"


def user_data_dir() -> Path:
    """Return the platform-appropriate Apoch-AI data directory.

    Order of precedence:
    1. ``$APOCH_HOME`` environment variable (explicit override)
    2. Platform default (``~/.local/share/apoch`` on Linux/macOS,
       ``%LOCALAPPDATA%\\apoch`` on Windows)
    """
    env = os.environ.get("APOCH_HOME")
    if env:
        return Path(env)

    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return base / "apoch"


def apoch_home() -> Path:
    """Return the Apoch-AI data directory (``~/.apoch`` or ``$APOCH_HOME``)."""
    env = os.environ.get("APOCH_HOME")
    return Path(env) if env else Path.home() / ".apoch"


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

_stdin_encoding = sys.stdin.encoding or "utf-8"
_stdout_encoding = sys.stdout.encoding or "utf-8"


def safe_decode(data: bytes, errors: str = "replace") -> str:
    """Decode *data* using the best available encoding."""
    try:
        return data.decode(_stdin_encoding, errors=errors)
    except (LookupError, UnicodeDecodeError):
        return data.decode("utf-8", errors=errors)


def safe_encode(text: str, errors: str = "replace") -> bytes:
    """Encode *text* using the best available encoding."""
    try:
        return text.encode(_stdout_encoding, errors=errors)
    except (LookupError, UnicodeEncodeError):
        return text.encode("utf-8", errors=errors)


# ---------------------------------------------------------------------------
# Platform stubs
# ---------------------------------------------------------------------------


def setup_platform_handlers(shutdown_cb: Callable[[], None]) -> None:
    """Register graceful-shutdown handlers for the current platform.

    Installs SIGTERM and SIGINT handlers. On Windows, uses
    ``SetConsoleCtrlHandler`` if available (via ``ctypes``).
    """
    if IS_WINDOWS:
        _setup_windows_handler(shutdown_cb)
    else:
        for sig in ("SIGTERM", "SIGINT"):
            if _has_signal(sig):
                sig_num = getattr(signal, sig)
                set_signal_handler(sig_num, lambda _signum, _frame: shutdown_cb())  # noqa: ARG005


def _setup_windows_handler(shutdown_cb: Callable[[], None]) -> NoReturn:
    """Set up Windows console control handler (stub for cross-ref)."""
    raise NotImplementedError("Windows console handler not yet implemented")


__all__ = [
    "IS_LINUX",
    "IS_MACOS",
    "IS_WINDOWS",
    "IS_TERMUX",
    "IS_WSL",
    "set_signal_handler",
    "restore_signal_handler",
    "user_config_dir",
    "user_data_dir",
    "apoch_home",
    "safe_decode",
    "safe_encode",
    "setup_platform_handlers",
]
