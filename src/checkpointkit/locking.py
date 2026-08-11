"""Cross-platform advisory locks for local durable state."""

from __future__ import annotations

import errno
import math
import os
import time
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

from .errors import LockTimeoutError

if os.name == "nt":  # pragma: no cover - selected and exercised on Windows CI
    import msvcrt
else:  # pragma: no cover - selected and exercised on POSIX CI
    import fcntl


def lock_path_for(path: str | os.PathLike[str]) -> Path:
    """Return the stable hidden sidecar lock path for a durable state document."""
    target = Path(path)
    return target.with_name(f".{target.name}.lock")


class FileLock:
    """Exclusive advisory lock backed by a one-byte sidecar file.

    The operating system releases the lock when the owning process exits. The
    sidecar file intentionally remains on disk. Every writer must cooperate by
    locking the same path; this is not a distributed lock and is not a tested
    coordination primitive for network filesystems.
    """

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        timeout: float = 10.0,
        poll_interval: float = 0.05,
    ) -> None:
        timeout_value = float(timeout)
        poll_value = float(poll_interval)
        if not math.isfinite(timeout_value) or timeout_value < 0:
            raise ValueError("Lock timeout must be a finite non-negative number")
        if not math.isfinite(poll_value) or poll_value <= 0:
            raise ValueError("Lock poll interval must be a finite positive number")
        self.path = Path(path)
        self.timeout = timeout_value
        self.poll_interval = poll_value
        self._handle: BinaryIO | None = None

    @staticmethod
    def _is_contention(exc: OSError) -> bool:
        if exc.errno in {
            errno.EACCES,
            errno.EAGAIN,
            getattr(errno, "EDEADLK", errno.EACCES),
        }:
            return True
        return getattr(exc, "winerror", None) in {33, 36}

    def _try_acquire(self, handle: BinaryIO) -> bool:
        handle.seek(0)
        try:
            if os.name == "nt":  # pragma: no cover - exercised on Windows CI
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if self._is_contention(exc):
                return False
            raise
        return True

    def _release(self, handle: BinaryIO) -> None:
        handle.seek(0)
        if os.name == "nt":  # pragma: no cover - exercised on Windows CI
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def __enter__(self) -> FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()

        deadline = time.monotonic() + self.timeout
        try:
            while not self._try_acquire(handle):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LockTimeoutError(
                        f"Timed out after {self.timeout:g}s waiting for lock: {self.path}"
                    )
                time.sleep(min(self.poll_interval, remaining))
        except BaseException:
            handle.close()
            raise

        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            self._release(handle)
        finally:
            handle.close()
