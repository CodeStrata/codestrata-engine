"""Paths for anonymous telemetry state under ~/.codestrata/."""

from __future__ import annotations

import os
from pathlib import Path

from codestrata.telemetry.constants import (
    HOME_ENV,
    INSTALLATION_ID_FILENAME,
    PREFERENCES_FILENAME,
    QUEUE_FILENAME,
)


def codestrata_home() -> Path:
    """Return the CodeStrata local state directory (never derived from repo)."""

    override = os.environ.get(HOME_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".codestrata"


def installation_id_path() -> Path:
    return codestrata_home() / INSTALLATION_ID_FILENAME


def preferences_path() -> Path:
    return codestrata_home() / PREFERENCES_FILENAME


def queue_path() -> Path:
    return codestrata_home() / QUEUE_FILENAME


def ensure_home() -> Path:
    home = codestrata_home()
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return home
