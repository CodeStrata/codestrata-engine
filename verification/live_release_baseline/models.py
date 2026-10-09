"""Typed records for the live Engine artifact and publisher inventory (E00.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ArtifactKind(StrEnum):
    WHEEL = "wheel"
    SDIST = "sdist"
    CONTAINER = "container"
    MIRROR_COMMIT = "mirror_commit"
    RELEASE_ASSET = "release_asset"
    GIT_TAG = "git_tag"


class PublisherStatus(StrEnum):
    """R01 is BLOCKED until an Engine-only OIDC publisher exists."""

    BLOCKED = "BLOCKED"
    PRESENT = "PRESENT"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"


class InferenceError(ValueError):
    """Raised when a live version would be taken from pyproject or git tags."""


@dataclass(frozen=True, slots=True)
class DistributedFile:
    filename: str
    packagetype: str
    sha256: str
    size: int
    url: str
    yanked: bool = False


@dataclass(frozen=True, slots=True)
class PyPIProject:
    name: str
    live_version: str
    versions: tuple[str, ...]
    files: tuple[DistributedFile, ...]
    yanked: bool = False


@dataclass(frozen=True, slots=True)
class GitIdentity:
    repository: str
    ref: str
    sha: str
    kind: ArtifactKind
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ContainerInquiry:
    registry: str
    repository: str
    status: CheckStatus
    digest: str | None
    http_status: int | None
    notes: str


@dataclass(frozen=True, slots=True)
class WorkflowSurface:
    path: str
    name: str
    triggers: tuple[str, ...]
    contents_write: bool
    id_token_write: bool
    aws_oidc: bool
    pypi_oidc_publish: bool
    container_publish: bool
    marketplace_publish: bool
    engine_only_publish: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class R01Inventory:
    status: PublisherStatus
    reason: str
    workflows: tuple[WorkflowSurface, ...]
    engine_only_oidc_publisher: str | None
    required_outside_engine_change: str


@dataclass(frozen=True, slots=True)
class InstallAttempt:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    installed_version: str | None
    observed_sha256: str | None


@dataclass(frozen=True, slots=True)
class InstallRollbackEvidence:
    install: InstallAttempt
    uninstall: InstallAttempt
    reinstall: InstallAttempt
    status: CheckStatus
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LiveReleaseRecord:
    inspected_at: str
    pypi: PyPIProject
    git_identities: tuple[GitIdentity, ...]
    containers: tuple[ContainerInquiry, ...]
    r01: R01Inventory
    install_rollback: InstallRollbackEvidence | None
    notes: tuple[str, ...] = field(default_factory=tuple)
    pyproject_version_ignored: str | None = None
    tags_not_used_as_live: tuple[str, ...] = ()
