"""Shared graph-domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class GraphType(StrEnum):
    """Identifies which CodeStrata graph a snapshot represents."""

    REPOSITORY = "repository"
    ENGINEERING_KNOWLEDGE = "engineering_knowledge"
    ASSESSMENT = "assessment"


class GraphStatus(StrEnum):
    """Lifecycle status for a persisted or in-memory graph snapshot."""

    BUILDING = "building"
    VALID = "valid"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


class GraphGenerationMode(StrEnum):
    """How a graph snapshot was produced."""

    FULL = "full"
    INCREMENTAL = "incremental"
    REUSED = "reused"
    MIGRATED = "migrated"


class ProvenanceSource(StrEnum):
    """Origin category for graph provenance records."""

    REPOSITORY_FILE = "repository_file"
    REPOSITORY_SYMBOL = "repository_symbol"
    DETERMINISTIC_ANALYZER = "deterministic_analyzer"
    STATIC_ANALYSIS_PROVIDER = "static_analysis_provider"
    ENGINEERING_KNOWLEDGE_PACK = "engineering_knowledge_pack"
    AI_AGENT = "ai_agent"
    HUMAN = "human"
    MIGRATION = "migration"
