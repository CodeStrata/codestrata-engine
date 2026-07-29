"""Stable identity helpers for Dependency Evidence (Phase 4.4.2)."""

from __future__ import annotations

from codestrata.domain.evidence.language.identifiers import stable_evidence_id

DEPENDENCY_EVIDENCE_SCHEMA_VERSION = "1.1.0"
DEPENDENCY_EVIDENCE_ARTIFACT_FILENAME = "dependency-evidence.json"
DEPENDENCY_EVIDENCE_ARTIFACT_SCHEMA_ID = "codestrata.dependency_evidence"

MAVEN_PROVIDER_ID = "dependency.maven.manifest"
MAVEN_PROVIDER_VERSION = "1.0.0"
GRADLE_PROVIDER_ID = "dependency.gradle.manifest"
GRADLE_PROVIDER_VERSION = "1.0.0"
PYTHON_PROVIDER_ID = "dependency.python.manifest"
PYTHON_PROVIDER_VERSION = "1.0.0"
COMPOSER_PROVIDER_ID = "dependency.composer.manifest"
COMPOSER_PROVIDER_VERSION = "1.0.0"
NUGET_PROVIDER_ID = "dependency.nuget.manifest"
NUGET_PROVIDER_VERSION = "1.0.0"


def make_manifest_evidence_id(*, provider_id: str, path: str) -> str:
    return stable_evidence_id("dependency.manifest", provider_id, path)


def make_declaration_evidence_id(
    *,
    provider_id: str,
    path: str,
    identity: str,
    kind: str,
    raw_version: str,
    profile: str,
    line: str,
) -> str:
    return stable_evidence_id(
        "dependency.declaration",
        provider_id,
        path,
        identity,
        kind,
        raw_version,
        profile,
        line,
    )
