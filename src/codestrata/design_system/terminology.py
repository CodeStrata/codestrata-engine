"""Canonical customer-facing terminology for CodeStrata.

Internal package names and CEIM acronyms may remain in code; product copy
should prefer these display terms.
"""

from __future__ import annotations

TERM_REPOSITORY = "Repository"
TERM_PORTFOLIO = "Portfolio"
TERM_ASSESSMENT = "Assessment"
TERM_ENGINEERING_ASSESSMENT = "Engineering Assessment"
TERM_ASSESSMENT_REPORT = "Assessment Report"
TERM_ENGINEERING_INTELLIGENCE = "Engineering Intelligence"
TERM_ENGINEERING_INTELLIGENCE_REPORT = "Engineering Intelligence Report"
TERM_EIR = "EIR"
TERM_ENGINEERING_KNOWLEDGE = "Engineering Knowledge"
TERM_ENGINEERING_SNAPSHOT = "Engineering Snapshot"
TERM_KNOWLEDGE_GRAPH = "Knowledge Graph"
TERM_ENGINEERING_KNOWLEDGE_GRAPH = "Engineering Knowledge Graph"
TERM_REPOSITORY_INTELLIGENCE = "Repository Intelligence"
TERM_PORTFOLIO_INTELLIGENCE = "Portfolio Intelligence"
TERM_EXECUTIVE_INTELLIGENCE = "Executive Intelligence"
TERM_STRATEGIC_ROADMAP = "Strategic Roadmap"
TERM_FINDING = "Finding"
TERM_RECOMMENDATION = "Recommendation"
TERM_EVIDENCE = "Evidence"
TERM_CITATION = "Citation"
TERM_CONFIDENCE = "Confidence"
TERM_COVERAGE = "Coverage"
TERM_LIMITATION = "Limitation"

# CEIM is the internal Canonical Engineering Intelligence Model; customer copy
# uses Engineering Snapshot.
CEIM_DISPLAY_NAME = TERM_ENGINEERING_SNAPSHOT

# Official product names (AI is a capability, never part of the product name).
PRODUCT_CODESTRATA = "CodeStrata"
PRODUCT_ENGINE = "CodeStrata Engine"
PRODUCT_PLATFORM = "CodeStrata Platform"
PRODUCT_VSCODE_EXTENSION = "CodeStrata VS Code Extension"
# Retired product display name — historical docs/reports only (Slice 12.4).
PRODUCT_CURSOR_EXTENSION = "CodeStrata Cursor Extension"

# Product-language scope (documentation authority; not a runtime dependency):
# - Engineering Assessment / Assessment Report → single repository
# - Engineering Intelligence / EIR → portfolio / multi-repository
# Do not use Engineering Intelligence as the name of the single-repo Engine CLI experience.

CANONICAL_TERMS: tuple[str, ...] = (
    TERM_REPOSITORY,
    TERM_PORTFOLIO,
    TERM_ASSESSMENT,
    TERM_ENGINEERING_ASSESSMENT,
    TERM_ASSESSMENT_REPORT,
    TERM_ENGINEERING_INTELLIGENCE,
    TERM_ENGINEERING_INTELLIGENCE_REPORT,
    TERM_EIR,
    TERM_ENGINEERING_KNOWLEDGE,
    TERM_ENGINEERING_SNAPSHOT,
    TERM_KNOWLEDGE_GRAPH,
    TERM_ENGINEERING_KNOWLEDGE_GRAPH,
    TERM_REPOSITORY_INTELLIGENCE,
    TERM_PORTFOLIO_INTELLIGENCE,
    TERM_EXECUTIVE_INTELLIGENCE,
    TERM_STRATEGIC_ROADMAP,
    TERM_FINDING,
    TERM_RECOMMENDATION,
    TERM_EVIDENCE,
    TERM_CITATION,
    TERM_CONFIDENCE,
    TERM_COVERAGE,
    TERM_LIMITATION,
)
