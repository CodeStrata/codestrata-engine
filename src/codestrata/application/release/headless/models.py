"""Headless run manifests and detached signature envelopes (E14.3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.contracts.serialization import require_content_digest


class HeadlessArtifactRef(BaseModel):
    """One emitted artifact bound by filename and content digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    filename: str
    schema_name: str
    content_digest: str

    @field_validator("content_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="artifact content_digest")


class HeadlessRunManifest(BaseModel):
    """Unsigned manifest listing standard headless artifacts. Signature is detached."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.headless-run-manifest.v1"
    schema_version: str = "1.0.0"
    invocation_digest: str
    effective_ruleset_digest: str
    package_purpose: str
    requested_purpose: str
    export_mode: str
    artifacts: tuple[HeadlessArtifactRef, ...]
    export_transmission_performed: bool = False
    hosted_calls_performed: bool = False
    consent_required: bool = False
    analysis_signer_isolated: bool = True

    @field_validator("invocation_digest", "effective_ruleset_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="manifest digest")


class DetachedResultSignature(BaseModel):
    """Operational signature metadata. Canonical manifest bytes are signed separately."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.headless-detached-signature.v1"
    schema_version: str = "1.0.0"
    manifest_digest: str
    profile_id: str = "codestrata.release.offline-self-managed-key.v1"
    signer_role: str = "private_result"
    key_id: str
    purpose: str
    algorithm: str = "ed25519"
    signature_b64: str
    signed_at: str

    @field_validator("manifest_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="manifest_digest")


class HeadlessRunOutcome(BaseModel):
    """Result of one neutral local invocation (analysis phase only unless signed=True)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    reason: str
    output_directory: str
    manifest: HeadlessRunManifest | None = None
    detached_signature: DetachedResultSignature | None = None
    admission_admitted: bool | None = None
    admission_reason: str | None = None
    job_terminal_state: str | None = None
    job_successful: bool | None = None


class HeadlessRunError(ValueError):
    """Headless invocation, package admission, or artifact emission failed."""
