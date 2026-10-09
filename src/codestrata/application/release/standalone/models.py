"""Release build, SBOM and provenance models (E14.2)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
CATALOG_PACKAGE_REVISION = "ENGINE-2026-09-15-R1"


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["wheel", "sdist", "sbom", "provenance", "runtime_lock"]
    filename: str
    sha256: str
    bytes: int


class SourceBinding(BaseModel):
    """Explicit source identity for a build. Git is not discovered here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["committed", "development"]
    source_sha: str | None = None
    source_root: str
    toolchain: str
    build_procedure: str
    note: str

    @model_validator(mode="after")
    def require_verified_commit(self) -> SourceBinding:
        if self.status == "committed":
            if self.source_sha is None or _COMMIT_SHA.fullmatch(self.source_sha) is None:
                raise ValueError("committed source binding requires a verified 40-hex sha")
            return self
        if self.source_sha is not None:
            raise ValueError("development builds must not carry a source sha")
        return self


class ReleaseProvenanceManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.release.provenance.v1"
    schema_version: str = "1.0.0"
    engine_version: str
    catalog_package_revision: str = CATALOG_PACKAGE_REVISION
    source_binding: SourceBinding
    artifacts: tuple[ArtifactRecord, ...]
    runtime_lock_digest: str
    operational_limits_profile_id: str
    operational_limits_digest: str
    sbom_digest: str

    def primary_artifact_digest(self, kind: Literal["wheel", "sdist"]) -> str | None:
        for item in self.artifacts:
            if item.kind == kind:
                return item.sha256
        return None


class SbomComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version_spec: str
    purl: str


class RuntimeSbom(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.release.runtime-sbom.v1"
    schema_version: str = "1.0.0"
    bom_format: str = "CycloneDX"
    spec_version: str = "1.5"
    components: tuple[SbomComponent, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackagingCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    ok: bool
    detail: str
    missing: tuple[str, ...] = ()


class LocalHealthStatus(BaseModel):
    """File-protocol health snapshot (no HTTP service)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.local-health.v1"
    schema_version: str = "1.0.0"
    ok: bool
    phase: str
    backend: str = "release-container"
    database: bool = False
    http_service: bool = False
    issues: tuple[str, ...] = ()


class OperationalAuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    kind: str
    message: str


class BuildVerificationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    engine_version: str
    provenance: ReleaseProvenanceManifest | None = None
    packaging_checks: tuple[PackagingCheckResult, ...] = ()
    install_outside_checkout: bool = False
    detail: str = ""
