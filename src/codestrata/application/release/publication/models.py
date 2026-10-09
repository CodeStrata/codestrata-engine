"""Publication preflight models (E14.4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.release.standalone.models import ReleaseProvenanceManifest


class CatalogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["wheel", "sdist", "sbom", "provenance", "container_recipe", "sigstore_bundle"]
    path: str
    sha256: str
    bytes: int


class PublicationCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.release.publication-catalog.v1"
    schema_version: str = "1.0.0"
    # E01.1 catalog label. Not the release source SHA.
    package_revision: str = "ENGINE-2026-09-15-R1"
    entries: tuple[CatalogEntry, ...]


class R01PreflightRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.release.r01-preflight.v1"
    schema_version: str = "1.0.0"
    status: Literal["BLOCKED", "PRESENT"]
    reason: str
    engine_only_oidc_publisher: str | None = None
    required_outside_engine_change: str = ""
    monorepo_ci_relabeled_as_publisher: bool = False
    publication_performed: bool = False


class PublicRehearsalRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.release.public-rehearsal.v1"
    schema_version: str = "1.0.0"
    artifact_kind: Literal["wheel"] = "wheel"
    artifact_sha256: str
    verification_status: str
    verification_reason: str
    expected_identity: str
    expected_issuer: str
    oidc_identity: str | None = None
    oidc_issuer: str | None = None
    transparency_log_used: bool = False


class PublicationPreflightSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.release.publication-preflight.v1"
    schema_version: str = "1.0.0"
    ok: bool
    build_ok: bool
    public_rehearsal_ok: bool
    r01_ready: bool
    detail: str
    provenance: ReleaseProvenanceManifest | None = None
    catalog: PublicationCatalog | None = None
    r01: R01PreflightRecord | None = None
    public_rehearsal: PublicRehearsalRecord | None = None
    limitations: tuple[str, ...] = Field(
        default=(
            "rehearsal_uses_offline_test_fulcio_material_not_live_oidc",
            "no_pypi_container_or_tag_publication_performed",
            "r01_blocked_requires_separate_outside_engine_authorization",
        )
    )
