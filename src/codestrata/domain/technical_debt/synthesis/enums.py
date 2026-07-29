"""Technical Debt synthesis enums (Phase 4.3.5)."""

from __future__ import annotations

from enum import StrEnum


class TechnicalDebtConclusionKind(StrEnum):
    """Bounded deterministic conclusion kinds."""

    COMPLEXITY_PRESENT = "complexity_present"
    THEME_COMPLEXITY = "theme_complexity"
    PACKAGE_CONCENTRATION = "package_concentration"
    HOTSPOT_CONCENTRATION = "hotspot_concentration"
    MULTI_RULE_HOTSPOTS = "multi_rule_hotspots"
    NO_PRODUCTION_FINDINGS = "no_production_findings"
    PARTIAL_COVERAGE = "partial_coverage"
    TEST_MAINTAINABILITY = "test_maintainability"
    DISABLED = "disabled"


class TechnicalDebtConclusionAudience(StrEnum):
    PRODUCTION_HEALTH = "production_health"
    TEST_OBSERVATION = "test_observation"
    COVERAGE = "coverage"
    STATUS = "status"


class TechnicalDebtSynthesisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
