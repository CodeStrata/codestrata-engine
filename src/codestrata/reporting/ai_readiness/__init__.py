"""AI Readiness Intelligence report presentation (Phase 4.8.6 + Epic 3 Slice 3.8)."""

from codestrata.reporting.ai_readiness.adapter import AiReadinessReportAdapter
from codestrata.reporting.ai_readiness.intelligence import build_ai_readiness_intelligence
from codestrata.reporting.ai_readiness.intelligence_models import (
    AI_READINESS_INTELLIGENCE_SECTION_ID,
    AI_READINESS_INTELLIGENCE_SECTION_VERSION,
    AiReadinessIntelligenceSection,
)
from codestrata.reporting.ai_readiness.models import (
    AI_READINESS_REPORT_SECTION_ID,
    AI_READINESS_REPORT_SECTION_VERSION,
    AiReadinessReportSection,
)

__all__ = [
    "AI_READINESS_INTELLIGENCE_SECTION_ID",
    "AI_READINESS_INTELLIGENCE_SECTION_VERSION",
    "AI_READINESS_REPORT_SECTION_ID",
    "AI_READINESS_REPORT_SECTION_VERSION",
    "AiReadinessIntelligenceSection",
    "AiReadinessReportAdapter",
    "AiReadinessReportSection",
    "build_ai_readiness_intelligence",
]
