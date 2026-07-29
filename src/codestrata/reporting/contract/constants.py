"""Report contract constants (Phase 5.12)."""

from __future__ import annotations

# Envelope versions remain 1.2 (additive top-level ``manifest`` only).
ASSESSMENT_JSON_SCHEMA_VERSION = "1.2"
ASSESSMENT_JSON_REPORT_VERSION = "1.2"
REPORT_HTML_VERSION = "3.0"
REPORT_CONTRACT_VERSION = "1.0.0"

# Paths excluded from structural determinism comparisons.
VOLATILE_JSON_PATHS: tuple[str, ...] = (
    "assessment.generated_at",
    "assessment.timing",
    "assessment.ai.latency_ms",
    "assessment.static_analysis",  # may include duration_ms per provider
    "manifest.generated_at",
)

OPTIONAL_ASSESSMENT_SECTIONS: tuple[str, ...] = (
    "architecture",
    "technical_debt",
    "dependency",
    "security",
    "testing",
    "cloud",
    "ai_readiness",
    "performance",
    "roadmap",
)

CORE_ENABLED_SECTIONS: tuple[str, ...] = (
    "executive_summary",
    "technologies",
    "findings",
    "recommendations",
)

ALLOWED_SEVERITIES: frozenset[str] = frozenset(
    {"critical", "high", "medium", "low", "info", "informational"}
)
ALLOWED_PRIORITIES: frozenset[str] = frozenset({"critical", "immediate", "high", "medium", "low"})
ALLOWED_EFFORTS: frozenset[str] = frozenset(
    {"xs", "s", "m", "l", "xl", "small", "medium", "large", "extra_large", "unknown"}
)
ALLOWED_RISKS: frozenset[str] = frozenset({"high", "medium", "low"})
ALLOWED_CONFIDENCE: frozenset[str] = frozenset({"high", "medium", "low", "none"})
