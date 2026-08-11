"""Clean environment helpers for first-time install verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path


# Variables that must not leak developer/monorepo context into the clean venv.
_STRIP_PREFIXES = (
    "AWS_",
    "OPENAI_",
    "BEDROCK_",
    "CODESTRATA_DATABASE",
    "VIRTUAL_ENV",
)

_STRIP_EXACT = (
    "PYTHONPATH",
    "PYTHONHOME",
    "PIP_REQUIRE_VIRTUALENV",
)


def scrub_environ(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment without developer install leakage."""

    source = dict(os.environ if base is None else base)
    cleaned: dict[str, str] = {}
    for key, value in source.items():
        if key in _STRIP_EXACT:
            continue
        if any(key.startswith(prefix) for prefix in _STRIP_PREFIXES):
            continue
        cleaned[key] = value
    # Explicitly ensure PYTHONPATH is absent.
    cleaned.pop("PYTHONPATH", None)
    cleaned.pop("PYTHONHOME", None)
    return cleaned


def venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_codestrata(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "codestrata.exe"
    return venv_dir / "bin" / "codestrata"


def with_venv_path(env: dict[str, str], venv_dir: Path) -> dict[str, str]:
    """Prepend the venv scripts directory to PATH."""

    scripts = venv_python(venv_dir).parent
    merged = dict(env)
    merged["PATH"] = str(scripts) + os.pathsep + merged.get("PATH", "")
    merged.pop("PYTHONPATH", None)
    return merged


def assert_clean_env(env: dict[str, str]) -> list[str]:
    """Return violation messages if the environment is not clean."""

    violations: list[str] = []
    if "PYTHONPATH" in env and env["PYTHONPATH"].strip():
        violations.append("PYTHONPATH must be unset for clean installation")
    if env.get("VIRTUAL_ENV") and "codestrata" in env.get("VIRTUAL_ENV", "").lower():
        # Allow the verification venv itself; reject pointing at a monorepo .venv by path
        # markers is handled by the runner using a temporary directory.
        pass
    return violations


def engine_root_from_package() -> Path:
    """Resolve the Engine repository root containing pyproject.toml."""

    # verification/cli_installation/environment.py → parents[2] == engine/
    return Path(__file__).resolve().parents[2]
