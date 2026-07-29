"""Architecture Intelligence rule identifiers (Phase 4.2.1)."""

from __future__ import annotations

PACK_ID = "architecture.core"
PACK_VERSION = "1.0.0"
PACK_TITLE = "Architecture Intelligence Core"
PACK_DESCRIPTION = (
    "Initial production architecture rule pack: dependency cycles, layering, "
    "coupling, concentration, framework leakage, and optional enterprise standards."
)

RULE_DEPENDENCY_CYCLE = "architecture.dependency-cycle"
RULE_INVALID_DEPENDENCY_DIRECTION = "architecture.invalid-dependency-direction"
RULE_LAYER_BOUNDARY_VIOLATION = "architecture.layer-boundary-violation"
RULE_EXCESSIVE_CROSS_MODULE_COUPLING = "architecture.excessive-cross-module-coupling"
RULE_COMPONENT_CONCENTRATION = "architecture.component-concentration"
RULE_FRAMEWORK_LEAKAGE = "architecture.framework-leakage"
RULE_ENTERPRISE_STANDARD_MISMATCH = "architecture.enterprise-standard-mismatch"

RULE_VERSION = "1.0.0"
