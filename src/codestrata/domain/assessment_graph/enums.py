"""Assessment Graph vocabulary.

The Assessment Graph is an assessment-scoped projection/reference graph. It
points at Repository Graph entities and Engineering Knowledge concepts without
copying their full property payloads.
"""

from __future__ import annotations

from enum import StrEnum


class AssessmentNodeType(StrEnum):
    """Canonical node kinds for the Assessment Graph."""

    REPOSITORY_ENTITY_REFERENCE = "repository_entity_reference"
    KNOWLEDGE_CONCEPT_REFERENCE = "knowledge_concept_reference"


class AssessmentRelationshipType(StrEnum):
    """Canonical relationship kinds for the Assessment Graph."""

    BINDS_TO_KNOWLEDGE = "binds_to_knowledge"
