"""Single-instance lock for ``--live`` (one process = one MemoryWorldState + one Tk root)."""

from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment, misc]

_LOCK_FH: object | None = None


def acquire_live_instance_lock() -> None:
    """
    Prevent a second ``python -m site_zero --live`` from starting.

    Each ``--live`` run uses in-process memory only for that process; a second window is a
    second simulation and will look \"out of sync\" with the first.
    """
    global _LOCK_FH
    if fcntl is None:
        return
    base = Path.home() / ".cache" / "site-zero"
    base.mkdir(parents=True, exist_ok=True)
    lock_path = base / "live.lock"
    fh = open(lock_path, "w", encoding="ascii", errors="replace")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        print(
            "Site-Zero: another `--live` instance is already running (separate process = separate world).\n"
            "Close the other window, or run:  pkill -f 'python -m site_zero'\n"
            "To watch the same world from two windows, use Redis: one terminal `python -m site_zero`, "
            "others `python -m site_zero --gui`.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    _LOCK_FH = fh
    fh.write(str(os.getpid()))
    fh.flush()
    atexit.register(release_live_instance_lock)


def release_live_instance_lock() -> None:
    global _LOCK_FH
    if _LOCK_FH is None or fcntl is None:
        return
    fh = _LOCK_FH
    _LOCK_FH = None
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        fh.close()
    except OSError:
        pass
