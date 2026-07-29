"""Safe loading of optional ``.env`` files for local developer onboarding.

Loads ``KEY=VALUE`` pairs into ``os.environ`` without overriding variables that
are already set in the process environment. Does not interpolate values, expand
shell syntax, execute commands, or follow network URLs.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_dotenv(
    *,
    start_directory: Path | None = None,
    filename: str = ".env",
    override: bool = False,
) -> Path | None:
    """Load the nearest ``.env`` file walking upward from ``start_directory``.

    Returns the path that was loaded, or ``None`` when no file was found.
    Existing environment variables win unless ``override`` is true.
    """

    directory = (start_directory or Path.cwd()).resolve()
    for candidate_dir in (directory, *directory.parents):
        path = candidate_dir / filename
        if path.is_file():
            apply_dotenv_file(path, override=override)
            return path
        # Stop at filesystem root after checking it once.
        if candidate_dir.parent == candidate_dir:
            break
    return None


def apply_dotenv_file(path: Path, *, override: bool = False) -> int:
    """Apply one ``.env`` file. Returns the number of keys newly applied."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0

    applied = 0
    for raw_line in text.splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if not override and key in os.environ:
            continue
        os.environ[key] = value
        applied += 1
    return applied


def _parse_dotenv_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    key = key.strip()
    if not _ENV_KEY.match(key):
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    # Reject shell/command interpolation markers rather than expanding them.
    if "${" in value or "$(" in value or "`" in value:
        return None
    return key, value
