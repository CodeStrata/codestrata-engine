"""Engineering Intelligence Summary (Epic 3 Slice 3.10).

Synthesis-only presentation projections across assessment heads.
"""

from codestrata.reporting.engineering_intelligence.intelligence import (
    build_engineering_intelligence,
    scrub_soft_engineering_claims,
)
from codestrata.reporting.engineering_intelligence.intelligence_models import (
    ENGINEERING_INTELLIGENCE_SECTION_ID,
    ENGINEERING_INTELLIGENCE_SECTION_VERSION,
    EngineeringIntelligenceSection,
)

__all__ = [
    "ENGINEERING_INTELLIGENCE_SECTION_ID",
    "ENGINEERING_INTELLIGENCE_SECTION_VERSION",
    "EngineeringIntelligenceSection",
    "build_engineering_intelligence",
    "scrub_soft_engineering_claims",
]
