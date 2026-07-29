"""CodeStrata Design System — shared tokens and product terminology.

Foundation for HTML reports and future dashboards, documentation, and
extensions. Customer-facing surfaces should import tokens from here rather
than duplicating palette or type rules.
"""

from __future__ import annotations

from codestrata.design_system.terminology import (
    CANONICAL_TERMS,
    TERM_ASSESSMENT,
    TERM_CITATION,
    TERM_CONFIDENCE,
    TERM_COVERAGE,
    TERM_ENGINEERING_SNAPSHOT,
    TERM_EVIDENCE,
    TERM_EXECUTIVE_INTELLIGENCE,
    TERM_FINDING,
    TERM_KNOWLEDGE_GRAPH,
    TERM_LIMITATION,
    TERM_PORTFOLIO,
    TERM_PORTFOLIO_INTELLIGENCE,
    TERM_RECOMMENDATION,
    TERM_REPOSITORY,
    TERM_REPOSITORY_INTELLIGENCE,
    TERM_STRATEGIC_ROADMAP,
)
from codestrata.design_system.tokens import DESIGN_TOKENS_CSS, DESIGN_TOKENS_VERSION

__all__ = [
    "CANONICAL_TERMS",
    "DESIGN_TOKENS_CSS",
    "DESIGN_TOKENS_VERSION",
    "TERM_ASSESSMENT",
    "TERM_CITATION",
    "TERM_CONFIDENCE",
    "TERM_COVERAGE",
    "TERM_ENGINEERING_SNAPSHOT",
    "TERM_EVIDENCE",
    "TERM_EXECUTIVE_INTELLIGENCE",
    "TERM_FINDING",
    "TERM_KNOWLEDGE_GRAPH",
    "TERM_LIMITATION",
    "TERM_PORTFOLIO",
    "TERM_PORTFOLIO_INTELLIGENCE",
    "TERM_RECOMMENDATION",
    "TERM_REPOSITORY",
    "TERM_REPOSITORY_INTELLIGENCE",
    "TERM_STRATEGIC_ROADMAP",
]
