"""Stable identity helpers for repository AI-readiness evidence (Phase 4.8.2)."""

from __future__ import annotations

import hashlib

from codestrata.domain.evidence.language.identifiers import stable_evidence_id

REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_NAME = "repository-ai-readiness-evidence"
REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_VERSION = "1.0.0"
REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_FILENAME = "repository-ai-readiness-evidence.json"
REPOSITORY_AI_READINESS_EVIDENCE_ARTIFACT_SCHEMA_ID = "codestrata.repository_ai_readiness_evidence"

PROVIDER_ID = "repository_ai_readiness.discovery"
PROVIDER_VERSION = "1.0.0"


def make_file_evidence_id(*, path: str, family: str) -> str:
    return (
        f"ai-readiness-file:{stable_evidence_id('repository_ai_readiness.file', path, family)[3:]}"
    )


def make_api_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "ai-readiness-api:"
        f"{stable_evidence_id('repository_ai_readiness.api', kind, path, basis)[3:]}"
    )


def make_docs_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "ai-readiness-docs:"
        f"{stable_evidence_id('repository_ai_readiness.docs', kind, path, basis)[3:]}"
    )


def make_data_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "ai-readiness-data:"
        f"{stable_evidence_id('repository_ai_readiness.data', kind, path, basis)[3:]}"
    )


def make_ai_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        f"ai-readiness-ai:{stable_evidence_id('repository_ai_readiness.ai', kind, path, basis)[3:]}"
    )


def make_tool_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "ai-readiness-tool:"
        f"{stable_evidence_id('repository_ai_readiness.tool', kind, path, basis)[3:]}"
    )


def make_workflow_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "ai-readiness-workflow:"
        f"{stable_evidence_id('repository_ai_readiness.workflow', kind, path, basis)[3:]}"
    )


def make_obs_evidence_id(*, kind: str, path: str, basis: str) -> str:
    return (
        "ai-readiness-obs:"
        f"{stable_evidence_id('repository_ai_readiness.obs', kind, path, basis)[3:]}"
    )


def make_diagnostic_id(*, code: str, path: str, detail: str) -> str:
    payload = f"{code}|{path}|{detail}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"ai-readiness-diagnostic:{digest}"


def make_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category}|{summary}".lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"ai-readiness-limitation:{digest}"


def make_bundle_id(*, repository_id: str, fingerprint: str) -> str:
    payload = f"{repository_id.strip()}|{fingerprint.strip()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"ai-readiness-evidence:{digest}"


def evidence_bundle_fingerprint(
    *,
    repository_id: str,
    record_ids: tuple[str, ...],
) -> str:
    payload = f"{repository_id.strip()}|" + ",".join(sorted(record_ids))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
