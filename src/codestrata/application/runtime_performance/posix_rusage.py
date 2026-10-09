"""Optional POSIX rusage access that must not fail to import on Windows."""

from __future__ import annotations

import sys
from types import ModuleType


def posix_resource_module() -> ModuleType | None:
    """Return the stdlib ``resource`` module when getrusage exists."""

    if sys.platform == "win32":
        return None
    try:
        import resource
    except ImportError:
        return None
    if not hasattr(resource, "getrusage") or not hasattr(resource, "RUSAGE_SELF"):
        return None
    return resource
