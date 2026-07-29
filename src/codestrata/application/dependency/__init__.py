"""Dependency Intelligence application package (Phase 4.4.1)."""

from codestrata.application.dependency.assessment import (
    DependencyAssessmentAssembler,
    create_dependency_assessment_assembler,
    dependency_assessment_section_enabled,
    dependency_pack_enabled,
)

__all__ = [
    "DependencyAssessmentAssembler",
    "create_dependency_assessment_assembler",
    "dependency_assessment_section_enabled",
    "dependency_pack_enabled",
]
