"""Stable identity helpers for repository performance evidence (Phase 4.9.2)."""

from __future__ import annotations

import hashlib

from codestrata.domain.evidence.language.identifiers import stable_evidence_id

REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_NAME = "repository-performance-evidence"
REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_VERSION = "1.0.0"
REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_FILENAME = "repository-performance-evidence.json"
REPOSITORY_PERFORMANCE_EVIDENCE_ARTIFACT_SCHEMA_ID = "codestrata.repository_performance_evidence"

PROVIDER_ID = "repository_performance.discovery"
PROVIDER_VERSION = "1.0.0"


def make_file_evidence_id(*, path: str, family: str) -> str:
    return f"perf-file:{stable_evidence_id('repository_performance.file', path, family)[3:]}"


def make_data_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return f"perf-data:{stable_evidence_id('repository_performance.data', kind, path, basis)[3:]}"


def make_blocking_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "perf-blocking:"
        f"{stable_evidence_id('repository_performance.blocking', kind, path, basis)[3:]}"
    )


def make_cache_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return f"perf-cache:{stable_evidence_id('repository_performance.cache', kind, path, basis)[3:]}"


def make_concurrency_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "perf-concurrency:"
        f"{stable_evidence_id('repository_performance.concurrency', kind, path, basis)[3:]}"
    )


def make_resource_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "perf-resource:"
        f"{stable_evidence_id('repository_performance.resource', kind, path, basis)[3:]}"
    )


def make_frontend_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "perf-frontend:"
        f"{stable_evidence_id('repository_performance.frontend', kind, path, basis)[3:]}"
    )


def make_obs_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return f"perf-obs:{stable_evidence_id('repository_performance.obs', kind, path, basis)[3:]}"


def make_config_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        f"perf-config:{stable_evidence_id('repository_performance.config', kind, path, basis)[3:]}"
    )


def make_diagnostic_id(*, code: str, path: str, detail: str) -> str:
    payload = f"{code}|{path}|{detail}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"perf-diagnostic:{digest}"


def make_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category}|{summary}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"perf-limitation:{digest}"


def make_bundle_id(*, repository_id: str, fingerprint: str) -> str:
    payload = f"{repository_id.strip()}|{fingerprint.strip()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"performance-evidence:{digest}"


def evidence_bundle_fingerprint(
    *,
    repository_id: str,
    record_ids: tuple[str, ...],
) -> str:
    payload = f"{repository_id.strip()}|" + ",".join(sorted(record_ids))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
