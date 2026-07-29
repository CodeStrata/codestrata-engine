"""Application language evidence package."""

from codestrata.application.evidence.language.factory import (
    create_language_evidence_service,
    language_evidence_pipeline_enabled,
)
from codestrata.application.evidence.language.service import LanguageEvidenceService

__all__ = [
    "LanguageEvidenceService",
    "create_language_evidence_service",
    "language_evidence_pipeline_enabled",
]
