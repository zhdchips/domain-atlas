"""Persistent data validation and cross-process maintenance locking."""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Render and supported local systems are POSIX.
    fcntl = None


class PersistentDataError(RuntimeError):
    """Raised when private data would not survive or cannot be written safely."""


def validate_private_data_directory(data_dir: Path, *, acknowledged: bool) -> Path:
    """Validate the explicit persistence contract before private mode initializes data."""
    if not data_dir.is_absolute():
        raise PersistentDataError("private_owner requires DATA_DIR to be an absolute path.")
    if not acknowledged:
        raise PersistentDataError(
            "private_owner requires PERSISTENT_DATA_ACKNOWLEDGED=true after mounting durable storage."
        )
    resolved = data_dir.expanduser().resolve()
    temporary_roots = {Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve()}
    if resolved in temporary_roots:
        raise PersistentDataError("private_owner DATA_DIR cannot be the system temporary directory.")
    resolved.mkdir(parents=True, exist_ok=True)
    probe = resolved / f".write-probe-{os.getpid()}-{threading.get_ident()}"
    renamed = probe.with_suffix(".ok")
    try:
        with probe.open("xb") as handle:
            handle.write(b"domain-atlas-persistence-check")
            handle.flush()
            os.fsync(handle.fileno())
        probe.replace(renamed)
        renamed.unlink()
    except OSError as exc:
        probe.unlink(missing_ok=True)
        renamed.unlink(missing_ok=True)
        raise PersistentDataError(
            f"private_owner DATA_DIR is not writable: {resolved}"
        ) from exc
    return resolved


class DataDirectoryLock:
    """Coordinate application writes and maintenance snapshots across processes."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.path = data_dir / ".domain-atlas.lock"
        self._fallback_lock = threading.RLock()

    @contextmanager
    def shared(self) -> Iterator[None]:
        with self._acquire(shared=True):
            yield

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        with self._acquire(shared=False):
            yield

    @contextmanager
    def _acquire(self, *, shared: bool) -> Iterator[None]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if fcntl is None:
            with self._fallback_lock:
                yield
            return
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
