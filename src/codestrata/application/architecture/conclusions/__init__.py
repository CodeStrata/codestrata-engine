"""Application architecture conclusions package."""

from codestrata.application.architecture.conclusions.factory import (
    architecture_conclusions_enabled,
    create_architecture_conclusion_service,
    empty_conclusion_result,
)
from codestrata.application.architecture.conclusions.result import ArchitectureConclusionResult
from codestrata.application.architecture.conclusions.service import ArchitectureConclusionService

__all__ = [
    "ArchitectureConclusionResult",
    "ArchitectureConclusionService",
    "architecture_conclusions_enabled",
    "create_architecture_conclusion_service",
    "empty_conclusion_result",
]
