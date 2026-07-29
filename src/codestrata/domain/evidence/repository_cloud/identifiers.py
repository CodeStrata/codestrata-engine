"""Stable identity helpers for repository-cloud evidence (Phase 4.7.2)."""

from __future__ import annotations

import hashlib

from codestrata.domain.evidence.language.identifiers import stable_evidence_id

REPOSITORY_CLOUD_EVIDENCE_SCHEMA_NAME = "repository-cloud-evidence"
REPOSITORY_CLOUD_EVIDENCE_SCHEMA_VERSION = "1.0.0"
REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_FILENAME = "repository-cloud-evidence.json"
REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_SCHEMA_ID = "codestrata.repository_cloud_evidence"

PROVIDER_ID = "repository_cloud.discovery"
PROVIDER_VERSION = "1.0.0"


def make_file_evidence_id(*, path: str, family: str) -> str:
    return f"cloud-file:{stable_evidence_id('repository_cloud.file', path, family)[3:]}"


def make_platform_evidence_id(*, platform: str, path: str, basis: str) -> str:
    return (
        "cloud-platform:"
        f"{stable_evidence_id('repository_cloud.platform', platform, path, basis)[3:]}"
    )


def make_container_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        f"cloud-container:{stable_evidence_id('repository_cloud.container', kind, path, basis)[3:]}"
    )


def make_orchestration_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return f"cloud-orch:{stable_evidence_id('repository_cloud.orch', kind, path, basis)[3:]}"


def make_iac_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return f"cloud-iac:{stable_evidence_id('repository_cloud.iac', kind, path, basis)[3:]}"


def make_serverless_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "cloud-serverless:"
        f"{stable_evidence_id('repository_cloud.serverless', kind, path, basis)[3:]}"
    )


def make_service_evidence_id(*, service: str, path: str, basis: str) -> str:
    return (
        f"cloud-service:{stable_evidence_id('repository_cloud.service', service, path, basis)[3:]}"
    )


def make_deployment_evidence_id(*, system: str, path: str, basis: str) -> str:
    return f"cloud-deploy:{stable_evidence_id('repository_cloud.deploy', system, path, basis)[3:]}"


def make_diagnostic_id(*, code: str, path: str, detail: str) -> str:
    payload = f"{code}|{path}|{detail}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"cloud-diagnostic:{digest}"


def make_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category}|{summary}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"cloud-limitation:{digest}"


def make_bundle_id(*, repository_id: str, fingerprint: str) -> str:
    payload = f"{repository_id.strip()}|{fingerprint.strip()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"cloud-evidence:{digest}"


def evidence_bundle_fingerprint(
    *,
    repository_id: str,
    record_ids: tuple[str, ...],
) -> str:
    payload = f"{repository_id.strip()}|" + ",".join(sorted(record_ids))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
