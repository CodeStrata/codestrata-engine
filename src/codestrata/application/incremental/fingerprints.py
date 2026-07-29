"""Enriched fingerprint models for incremental planning.

Domain ``FileFingerprint`` / ``RepositoryFingerprint`` remain content-digest
value objects. These planning models add optional structural/dependency hashes
and engine compatibility fields without rewriting immutable blobs.

Structural and dependency hashes are ``None`` until scanners produce them
safely. Missing hashes reduce reuse eligibility rather than counting as matches.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata import RULESET_VERSION, __version__
from codestrata.domain.assessment_graph import ASSESSMENT_GRAPH_SCHEMA_VERSION
from codestrata.domain.engineering_knowledge import ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION
from codestrata.domain.recommendations import RECOMMENDATION_RESULT_VERSION
from codestrata.domain.repository.enums import RepositoryFileKind
from codestrata.domain.repository.files import RepositoryFileEntry
from codestrata.domain.repository.fingerprints import RepositoryFingerprintFactory
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.domain.repository_graph import REPOSITORY_GRAPH_SCHEMA_VERSION

# Stable functional fingerprints for registered components (not package patch alone).
SCANNER_FINGERPRINT = "scanner:inventory-v1"
PARSER_FINGERPRINT = "parser:filename-language-v1"
GRAPH_BUILDER_FINGERPRINT = "graph-builder:pipeline-v1.0.0"
RULE_ENGINE_FINGERPRINT = f"rules:{RULESET_VERSION}"
RECOMMENDATION_ENGINE_FINGERPRINT = f"recommendations:{RECOMMENDATION_RESULT_VERSION}"
FINDINGS_ARTIFACT_SCHEMA = "1.0.0"


class PlanningFileFingerprint(BaseModel):
    """Per-file fingerprint enrichment for incremental planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    content_hash: str
    size_bytes: int = Field(ge=0)
    language: str | None = None
    file_kind: RepositoryFileKind = RepositoryFileKind.UNKNOWN
    structural_hash: str | None = None
    dependency_hash: str | None = None
    metadata_hash: str | None = None


class AssessmentContentFingerprint(BaseModel):
    """Repository-level fingerprint used for incremental compatibility."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_hash: str
    technology_fingerprint: str | None = None
    scanner_fingerprint: str
    parser_fingerprint: str
    graph_builder_fingerprint: str
    rule_engine_fingerprint: str
    recommendation_engine_fingerprint: str
    artifact_schema_versions: dict[str, str] = Field(default_factory=dict)
    tool_version: str


class EngineCompatibilityFingerprint(BaseModel):
    """Deterministic engine compatibility fingerprint (no timestamps)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scanner: str
    parsers: dict[str, str] = Field(default_factory=dict)
    repository_graph_schema: str
    knowledge_graph_schema: str
    assessment_graph_schema: str
    graph_builder: str
    rules: str
    recommendations: str
    artifact_schemas: dict[str, str] = Field(default_factory=dict)
    tool_version: str


def metadata_hash_for_entry(entry: RepositoryFileEntry) -> str:
    """Deterministic hash of extraction-relevant metadata (not content)."""

    payload = {
        "executable": entry.executable,
        "file_kind": entry.file_kind.value,
        "generated": entry.generated,
        "language": entry.language,
        "media_type": entry.media_type,
        "size_bytes": entry.size_bytes,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def planning_file_fingerprint(entry: RepositoryFileEntry) -> PlanningFileFingerprint:
    """Build a planning fingerprint from an inventory entry.

    Structural and dependency hashes remain ``None`` until scanners produce them.
    """

    return PlanningFileFingerprint(
        path=entry.path.root,
        content_hash=f"{entry.fingerprint.algorithm.value}:{entry.fingerprint.digest}",
        size_bytes=entry.size_bytes,
        language=entry.language,
        file_kind=entry.file_kind,
        structural_hash=None,
        dependency_hash=None,
        metadata_hash=metadata_hash_for_entry(entry),
    )


def current_engine_fingerprint() -> EngineCompatibilityFingerprint:
    """Return the current process engine fingerprint from stable constants."""

    return EngineCompatibilityFingerprint(
        scanner=SCANNER_FINGERPRINT,
        parsers={"default": PARSER_FINGERPRINT},
        repository_graph_schema=REPOSITORY_GRAPH_SCHEMA_VERSION,
        knowledge_graph_schema=ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
        assessment_graph_schema=ASSESSMENT_GRAPH_SCHEMA_VERSION,
        graph_builder=GRAPH_BUILDER_FINGERPRINT,
        rules=RULE_ENGINE_FINGERPRINT,
        recommendations=RECOMMENDATION_ENGINE_FINGERPRINT,
        artifact_schemas={
            "repository_graph": REPOSITORY_GRAPH_SCHEMA_VERSION,
            "engineering_knowledge_graph": ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
            "assessment_graph": ASSESSMENT_GRAPH_SCHEMA_VERSION,
            "findings": FINDINGS_ARTIFACT_SCHEMA,
            "recommendations": RECOMMENDATION_RESULT_VERSION,
        },
        tool_version=__version__,
    )


def assessment_content_fingerprint(
    manifest: RepositoryManifest,
    *,
    technology_fingerprint: str | None = None,
    engine: EngineCompatibilityFingerprint | None = None,
) -> AssessmentContentFingerprint:
    """Build a repository assessment fingerprint from a manifest + engine."""

    engine = engine or current_engine_fingerprint()
    content = RepositoryFingerprintFactory.from_manifest(manifest)
    return AssessmentContentFingerprint(
        manifest_hash=f"{content.algorithm.value}:{content.digest}",
        technology_fingerprint=technology_fingerprint,
        scanner_fingerprint=engine.scanner,
        parser_fingerprint=engine.parsers.get("default", PARSER_FINGERPRINT),
        graph_builder_fingerprint=engine.graph_builder,
        rule_engine_fingerprint=engine.rules,
        recommendation_engine_fingerprint=engine.recommendations,
        artifact_schema_versions=dict(sorted(engine.artifact_schemas.items())),
        tool_version=engine.tool_version,
    )


def fingerprint_digest(payload: dict[str, Any]) -> str:
    """Stable SHA-256 of a JSON-serializable mapping."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
