"""Lightweight fallback implementations of :mod:`filelock` primitives.

This project relies on :class:`filelock.FileLock` for coordinating access to
file-backed state.  The real dependency is small, but it is not available in the
execution environment used by the kata tests.  To keep the public API
compatible while avoiding an additional dependency during testing, we provide a
minimal drop-in replacement that mimics the behaviour we rely on.

The implementation intentionally keeps the surface area tiny – just the
``FileLock`` class and ``Timeout`` exception – and focuses on correctness for
single-process access with best-effort inter-process safety.  The lock is backed
by the presence of a ``.lock`` file and uses ``os.O_EXCL`` to ensure atomic
creation.  When the timeout elapses a ``Timeout`` exception is raised, matching
the semantics of the upstream library.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Optional

__all__ = ["FileLock", "Timeout"]


class Timeout(TimeoutError):
    """Raised when acquiring a lock exceeds the configured timeout."""


@dataclass
class FileLock:
    """Simple file-backed lock mirroring :class:`filelock.FileLock`.

    Parameters
    ----------
    path:
        Path to the lock file.  The parent directory is created if it does not
        already exist.
    timeout:
        Number of seconds to wait when acquiring the lock before raising
        :class:`Timeout`.  ``None`` means wait forever.
    poll_interval:
        Sleep duration (seconds) between retries while waiting for the lock.
    """

    path: str | os.PathLike[str]
    timeout: Optional[float] = 5.0
    poll_interval: float = 0.1

    def __post_init__(self) -> None:
        self._path = Path(self.path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._timeout = None if self.timeout is None else max(0.0, float(self.timeout))
        self._poll_interval = max(0.01, float(self.poll_interval))
        self._fd: Optional[int] = None

    # ------------------------------------------------------------------
    # Public API inspired by ``filelock``
    def acquire(self, timeout: Optional[float] = None, poll_interval: Optional[float] = None) -> bool:
        deadline: Optional[float]
        if timeout is None:
            effective_timeout = self._timeout
        else:
            effective_timeout = max(0.0, float(timeout))

        if effective_timeout is None:
            deadline = None
        else:
            deadline = monotonic() + effective_timeout

        interval = self._poll_interval if poll_interval is None else max(0.01, float(poll_interval))

        while True:
            try:
                self._fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, str(os.getpid()).encode("ascii", "ignore"))
                return True
            except FileExistsError:
                if deadline is not None and monotonic() > deadline:
                    raise Timeout(f"Timeout while waiting for lock: {self._path}")
                time.sleep(interval)

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            # Missing lock files should not crash consumers – another process
            # may have cleaned up after a crash.  We swallow the error to keep
            # the behaviour in line with ``filelock``.
            pass

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.release()

    # Convenience helpers -------------------------------------------------
    @property
    def is_locked(self) -> bool:
        return self._fd is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"FileLock(path={self._path!s}, locked={self.is_locked})"
