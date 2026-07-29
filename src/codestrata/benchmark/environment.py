"""Environment capture for benchmark artifacts."""

from __future__ import annotations

import os
import platform
import sys
from typing import Any


def capture_environment() -> dict[str, Any]:
    """Return a stable, non-secret environment snapshot."""

    codestrata_version = "unknown"
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            codestrata_version = version("codestrata")
        except PackageNotFoundError:
            codestrata_version = "development"
    except Exception:  # noqa: BLE001 - best-effort
        codestrata_version = "unknown"

    return {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "codestrata_version": codestrata_version,
        "cwd": os.getcwd(),
    }
