"""Typed records for published-artifact smoke (E16.3 / G52)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SmokeDecision(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class SmokeTargets:
    schema_version: int
    story: str
    package_revision: str
    pypi_project: str
    candidate_semver: str
    rollback_semver: str
    rollback_wheel_sha256: str
    candidate_wheel_sha256: str
    observation_business_days: int
    release_support_owner: str
    platform_webapp_owners_after_smoke: str


@dataclass(frozen=True, slots=True)
class RepresentativeSmokePin:
    role: str
    repository_id: str
    github_repository: str
    github_url: str
    pin_sha: str
    depth_class: str
    language: str


@dataclass(frozen=True, slots=True)
class SmokeReadiness:
    decision: SmokeDecision
    pypi_versions: tuple[str, ...]
    candidate_on_pypi: bool
    candidate_digest_recorded: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InstalledPublished:
    semver: str
    wheel_sha256: str
    wheel_path: str
    codestrata: str
    python: str
    workspace: str
    env: dict[str, str]
