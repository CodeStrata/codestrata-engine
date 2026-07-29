"""Repository Graph extraction orchestration enums."""

from __future__ import annotations

from enum import StrEnum


class RepositoryExtractionScope(StrEnum):
    """Whether extraction covers the full inventory or a change set only."""

    FULL = "full"
    INCREMENTAL = "incremental"


class ExtractionDiagnosticSeverity(StrEnum):
    """Severity for extractor observations that are not hard failures."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
