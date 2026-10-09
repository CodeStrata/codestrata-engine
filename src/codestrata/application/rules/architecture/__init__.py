"""Architecture Intelligence package (Phase 4.2.1)."""

from codestrata.application.rules.architecture.pack import ArchitectureRulePack, architecture_rules
from codestrata.application.rules.architecture.registration import register_architecture_pack
from codestrata.application.rules.architecture.view_builder import (
    build_architecture_analysis_view,
    find_directed_cycles,
    select_primary_unit,
)
from codestrata.application.rules.architecture.yaml_catalog import (
    ARCHITECTURE_LAUNCH_RULE_IDS,
    architecture_catalog_digests,
    architecture_catalog_entries,
)
from codestrata.application.rules.architecture.yaml_rules import evaluate_architecture_launch

__all__ = [
    "ARCHITECTURE_LAUNCH_RULE_IDS",
    "ArchitectureRulePack",
    "architecture_catalog_digests",
    "architecture_catalog_entries",
    "architecture_rules",
    "build_architecture_analysis_view",
    "evaluate_architecture_launch",
    "find_directed_cycles",
    "register_architecture_pack",
    "select_primary_unit",
]
