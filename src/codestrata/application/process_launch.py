"""Environment for a child process that imports this codestrata package.

The path is the parent of the imported ``codestrata`` package. That is
``site-packages`` for an installed wheel and the source ``src`` directory
during tests. It is not a sibling checkout and it does not add Platform.
"""

from __future__ import annotations

import os
from pathlib import Path


def package_import_root() -> str:
    import codestrata

    return str(Path(codestrata.__file__).resolve().parent.parent)


def child_process_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Copy ``base`` and ensure the child can import this package."""

    env = dict(os.environ if base is None else base)
    root = package_import_root()
    current = [item for item in env.get("PYTHONPATH", "").split(os.pathsep) if item]
    if root not in current:
        current.insert(0, root)
    env["PYTHONPATH"] = os.pathsep.join(current)
    return env
