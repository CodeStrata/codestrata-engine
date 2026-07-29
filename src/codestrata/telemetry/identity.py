"""Random anonymous installation identity (UUID v4)."""

from __future__ import annotations

import uuid
from pathlib import Path

from codestrata.telemetry.paths import ensure_home, installation_id_path


def _is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4


def generate_installation_id() -> str:
    """Return a fresh random UUID v4 (never derived from machine identity)."""

    return str(uuid.uuid4())


def read_installation_id(*, path: Path | None = None) -> str | None:
    target = path or installation_id_path()
    if not target.is_file():
        return None
    try:
        value = target.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not value or not _is_uuid4(value):
        return None
    return value


def write_installation_id(value: str, *, path: Path | None = None) -> Path:
    if not _is_uuid4(value):
        raise ValueError("installation id must be a UUID v4")
    ensure_home()
    target = path or installation_id_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value + "\n", encoding="utf-8")
        target.chmod(0o600)
    except OSError as error:
        raise OSError(f"unable to persist installation id: {error}") from error
    return target


def ensure_installation_id(*, path: Path | None = None) -> tuple[str, bool]:
    """Return ``(installation_id, created)`` creating a UUID v4 on first use."""

    existing = read_installation_id(path=path)
    if existing:
        return existing, False
    created = generate_installation_id()
    write_installation_id(created, path=path)
    return created, True


def reset_installation_id(*, path: Path | None = None) -> str:
    """Replace the installation id with a new UUID v4."""

    created = generate_installation_id()
    write_installation_id(created, path=path)
    return created
