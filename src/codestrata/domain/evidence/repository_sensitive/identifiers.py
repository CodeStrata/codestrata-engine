"""Stable identity helpers for repository-sensitive evidence (Phase 4.5.2)."""

from __future__ import annotations

import hashlib

from codestrata.domain.evidence.language.identifiers import stable_evidence_id

REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_NAME = "repository-sensitive-evidence"
REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION = "1.1.0"
REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_FILENAME = "repository-sensitive-evidence.json"
REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_SCHEMA_ID = (
    "codestrata.repository_sensitive_evidence"
)

ARTIFACT_PROVIDER_ID = "repository_sensitive.artifact.discovery"
ARTIFACT_PROVIDER_VERSION = "1.0.0"
CONFIGURATION_PROVIDER_ID = "repository_sensitive.configuration.literals"
CONFIGURATION_PROVIDER_VERSION = "1.0.0"


def make_artifact_evidence_id(*, path: str, kind: str) -> str:
    return stable_evidence_id("repository_sensitive.artifact", path, kind)


def make_configuration_evidence_id(
    *,
    path: str,
    normalized_key: str,
    section: str,
    line: str,
) -> str:
    return stable_evidence_id(
        "repository_sensitive.configuration",
        path,
        normalized_key,
        section,
        line,
    )


def make_diagnostic_id(*, code: str, path: str, detail: str) -> str:
    payload = f"{code}|{path}|{detail}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"rs-diagnostic:{digest}"


def make_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category}|{summary}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"rs-limitation:{digest}"


def fingerprint_value(value: str) -> str:
    """Deterministic cryptographic fingerprint of a literal value."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fingerprint_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def evidence_bundle_fingerprint(
    *,
    repository_id: str,
    artifact_ids: tuple[str, ...],
    configuration_ids: tuple[str, ...],
) -> str:
    payload = (
        f"{repository_id.strip()}|"
        + ",".join(sorted(artifact_ids))
        + "|"
        + ",".join(sorted(configuration_ids))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
