"""Stable identity helpers for repository-testing evidence (Phase 4.6.2)."""

from __future__ import annotations

import hashlib

from codestrata.domain.evidence.language.identifiers import stable_evidence_id

REPOSITORY_TESTING_EVIDENCE_SCHEMA_NAME = "repository-testing-evidence"
REPOSITORY_TESTING_EVIDENCE_SCHEMA_VERSION = "1.0.0"
REPOSITORY_TESTING_EVIDENCE_ARTIFACT_FILENAME = "repository-testing-evidence.json"
REPOSITORY_TESTING_EVIDENCE_ARTIFACT_SCHEMA_ID = (
    "codestrata.repository_testing_evidence"
)

PROVIDER_ID = "repository_testing.discovery"
PROVIDER_VERSION = "1.0.0"


def make_file_evidence_id(*, path: str, role: str) -> str:
    return f"test-file:{stable_evidence_id('repository_testing.file', path, role)[3:]}"


def make_framework_evidence_id(*, framework: str, path: str, basis: str) -> str:
    return (
        "test-framework:"
        f"{stable_evidence_id('repository_testing.framework', framework, path, basis)[3:]}"
    )


def make_type_evidence_id(*, test_type: str, path: str, basis: str) -> str:
    return (
        "test-type:"
        f"{stable_evidence_id('repository_testing.type', test_type, path, basis)[3:]}"
    )


def make_config_evidence_id(*, path: str, kind: str, detail: str) -> str:
    return (
        "test-config:"
        f"{stable_evidence_id('repository_testing.config', path, kind, detail)[3:]}"
    )


def make_marker_evidence_id(*, path: str, marker: str, line: str) -> str:
    return (
        "test-marker:"
        f"{stable_evidence_id('repository_testing.marker', path, marker, line)[3:]}"
    )


def make_fixture_evidence_id(*, path: str, kind: str) -> str:
    return (
        "test-fixture:"
        f"{stable_evidence_id('repository_testing.fixture', path, kind)[3:]}"
    )


def make_coverage_evidence_id(*, path: str, kind: str) -> str:
    return (
        "test-coverage:"
        f"{stable_evidence_id('repository_testing.coverage', path, kind)[3:]}"
    )


def make_ci_evidence_id(*, path: str, job: str, tool: str) -> str:
    return (
        "test-ci:"
        f"{stable_evidence_id('repository_testing.ci', path, job, tool)[3:]}"
    )


def make_diagnostic_id(*, code: str, path: str, detail: str) -> str:
    payload = f"{code}|{path}|{detail}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"test-diagnostic:{digest}"


def make_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category}|{summary}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"test-limitation:{digest}"


def make_bundle_id(*, repository_id: str, fingerprint: str) -> str:
    payload = f"{repository_id.strip()}|{fingerprint.strip()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"test-evidence:{digest}"


def evidence_bundle_fingerprint(
    *,
    repository_id: str,
    record_ids: tuple[str, ...],
) -> str:
    payload = f"{repository_id.strip()}|" + ",".join(sorted(record_ids))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
