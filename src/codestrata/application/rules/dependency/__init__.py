"""Dependency Intelligence SharedRule pack (Phase 4.4.3)."""

from __future__ import annotations

from codestrata.application.rules.dependency.assessment import (
    DependencyPackExecutionResult,
    dependency_evidence_collection_enabled,
    evaluate_dependency_pack,
    evaluate_dependency_pack_detailed,
)
from codestrata.application.rules.dependency.pack import DependencyRulePack, dependency_rules
from codestrata.application.rules.dependency.registration import register_dependency_pack

__all__ = [
    "DependencyPackExecutionResult",
    "DependencyRulePack",
    "dependency_evidence_collection_enabled",
    "dependency_rules",
    "evaluate_dependency_pack",
    "evaluate_dependency_pack_detailed",
    "register_dependency_pack",
]
