"""Persist repository-sensitive evidence artifacts (Phase 4.5.2)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.evidence.repository_sensitive.identifiers import (
    REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_SCHEMA_ID,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_RAW_PEM_BODY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----\s+[A-Za-z0-9+/=\n]{16,}\s+"
    r"-----END [A-Z0-9 ]*PRIVATE KEY-----"
)


class RepositorySensitiveEvidenceArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    artifact_count: int = Field(ge=0)
    configuration_fact_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)


class RawSecretPersistError(ValueError):
    """Raised when a raw secret would be written to persisted evidence."""


def assert_redacted_payload(text: str, *, extra_canaries: Sequence[str] = ()) -> None:
    """Refuse to persist raw private-key bodies or test canaries."""

    if _RAW_PEM_BODY.search(text):
        raise RawSecretPersistError("raw private-key body must not be persisted")
    for canary in extra_canaries:
        if canary and canary in text:
            raise RawSecretPersistError("raw secret canary must not be persisted")


def repository_sensitive_evidence_payload(
    evidence: AggregatedRepositorySensitiveEvidence,
) -> dict[str, object]:
    payload = evidence.model_dump(mode="json")
    payload["artifact_schema_id"] = REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_SCHEMA_ID
    return payload


def write_repository_sensitive_evidence_artifact(
    evidence: AggregatedRepositorySensitiveEvidence,
    run_directory: Path,
    *,
    extra_canaries: Sequence[str] = (),
) -> RepositorySensitiveEvidenceArtifactWriteResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_FILENAME
    text = dumps_stable_json(repository_sensitive_evidence_payload(evidence))
    assert_redacted_payload(text, extra_canaries=extra_canaries)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return RepositorySensitiveEvidenceArtifactWriteResult(
        path=path,
        artifact_count=len(evidence.artifacts),
        configuration_fact_count=len(evidence.configuration_facts),
        byte_size=len(text.encode("utf-8")),
    )
