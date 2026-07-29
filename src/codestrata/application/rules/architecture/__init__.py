"""Architecture Intelligence package (Phase 4.2.1)."""

from codestrata.application.rules.architecture.pack import ArchitectureRulePack, architecture_rules
from codestrata.application.rules.architecture.registration import register_architecture_pack
from codestrata.application.rules.architecture.view_builder import (
    build_architecture_analysis_view,
    find_directed_cycles,
    select_primary_unit,
)

__all__ = [
    "ArchitectureRulePack",
    "architecture_rules",
    "build_architecture_analysis_view",
    "find_directed_cycles",
    "register_architecture_pack",
    "select_primary_unit",
]
