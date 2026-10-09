"""Optional POSIX fcntl access that must not fail to import on Windows."""

from __future__ import annotations

import sys
from typing import Protocol, cast


class PosixFcntlModule(Protocol):
    """Subset of stdlib ``fcntl`` used for repository file locks."""

    LOCK_EX: int
    LOCK_NB: int
    LOCK_UN: int

    def flock(self, fd: int, operation: int) -> None: ...


def posix_fcntl_module() -> PosixFcntlModule | None:
    """Return the stdlib ``fcntl`` module when flock exists."""

    if sys.platform == "win32":
        return None
    try:
        import fcntl
    except ImportError:
        return None
    if not hasattr(fcntl, "flock"):
        return None
    return cast(PosixFcntlModule, fcntl)
