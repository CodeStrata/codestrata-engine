"""Modernization Assessment Intelligence (Epic 3 Slice 3.9).

Synthesis-only presentation projections. Does not invent Priority Actions,
roadmap initiatives, or AI narrative.
"""

from codestrata.reporting.modernization.intelligence import (
    build_modernization_intelligence,
    scrub_soft_modernization_claims,
)
from codestrata.reporting.modernization.intelligence_models import (
    MODERNIZATION_INTELLIGENCE_SECTION_ID,
    MODERNIZATION_INTELLIGENCE_SECTION_VERSION,
    ModernizationIntelligenceSection,
)

__all__ = [
    "MODERNIZATION_INTELLIGENCE_SECTION_ID",
    "MODERNIZATION_INTELLIGENCE_SECTION_VERSION",
    "ModernizationIntelligenceSection",
    "build_modernization_intelligence",
    "scrub_soft_modernization_claims",
]
