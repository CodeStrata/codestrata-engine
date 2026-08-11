"""Local persistence for anonymous installation identity (Epic 10 Slice 10.2)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
)
from codestrata.telemetry.analytics.installation_identity_errors import (
    InstallationIdentityError,
    InstallationIdentityErrorCode,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    IDENTITY_FILENAME,
    CommunityAnonymousInstallationIdentityPolicy,
    default_installation_identity_policy,
)
from codestrata.telemetry.paths import codestrata_home, ensure_home


def installation_identity_path(
    *,
    home: Path | None = None,
    policy: CommunityAnonymousInstallationIdentityPolicy | None = None,
) -> Path:
    active = policy or default_installation_identity_policy()
    root = home if home is not None else codestrata_home()
    return root / active.filename


def read_identity_bytes(*, path: Path) -> bytes | None:
    """Safe concurrent read — returns None when missing or unreadable."""

    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def write_identity_atomic(
    record: AnonymousInstallationIdentity,
    *,
    path: Path,
) -> None:
    """Atomically persist the identity record (temp file + replace)."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            record.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{IDENTITY_FILENAME}.",
            dir=str(path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            try:
                path.chmod(0o600)
            except OSError:
                pass
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
    except OSError as error:
        raise InstallationIdentityError(
            InstallationIdentityErrorCode.PERSISTENCE_FAILED
        ) from error


def ensure_identity_home(*, home: Path | None = None) -> Path:
    if home is not None:
        try:
            home.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise InstallationIdentityError(
                InstallationIdentityErrorCode.PERSISTENCE_FAILED
            ) from error
        return home
    return ensure_home()


__all__ = [
    "ensure_identity_home",
    "installation_identity_path",
    "read_identity_bytes",
    "write_identity_atomic",
]
