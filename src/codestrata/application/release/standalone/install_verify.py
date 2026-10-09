"""Pure helpers for clean install verification outside the Engine checkout."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InstallEnvironmentCheck:
    ok: bool
    detail: str


_FORBIDDEN_ENV = ("PYTHONPATH", "CODESTRATA_ENGINE_SRC")
_DB_IMPORT_MARKERS = (
    re.compile(r"\bsqlalchemy\b", re.I),
    re.compile(r"\bsqlite3\b"),
)


def verify_install_environment(environ: dict[str, str]) -> InstallEnvironmentCheck:
    for key in _FORBIDDEN_ENV:
        if key in environ and environ[key].strip():
            return InstallEnvironmentCheck(
                ok=False,
                detail=f"{key} must be unset for standalone install verification",
            )
    return InstallEnvironmentCheck(ok=True, detail="no monorepo PYTHONPATH markers")


def version_output_implies_database_dependency(output: str) -> bool:
    return any(marker.search(output) for marker in _DB_IMPORT_MARKERS)


def scrubbed_environ(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    for key in list(env):
        if key in _FORBIDDEN_ENV:
            env.pop(key, None)
    return env
