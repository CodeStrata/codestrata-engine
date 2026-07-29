"""Canonical phase display constants for the modernization roadmap."""

from __future__ import annotations

from codestrata.domain.roadmap.enums import RoadmapPhaseName

PHASE_SEQUENCE: tuple[RoadmapPhaseName, ...] = (
    RoadmapPhaseName.STABILIZE,
    RoadmapPhaseName.SECURE,
    RoadmapPhaseName.MODERNIZE,
    RoadmapPhaseName.OPTIMIZE,
)

PHASE_TITLES: dict[RoadmapPhaseName, str] = {
    RoadmapPhaseName.STABILIZE: "Stabilize",
    RoadmapPhaseName.SECURE: "Secure",
    RoadmapPhaseName.MODERNIZE: "Modernize",
    RoadmapPhaseName.OPTIMIZE: "Optimize",
}

PHASE_OBJECTIVES: dict[RoadmapPhaseName, str] = {
    RoadmapPhaseName.STABILIZE: (
        "Restore foundational engineering hygiene so later change is safe and observable."
    ),
    RoadmapPhaseName.SECURE: (
        "Reduce repository-sensitive security exposure before broader modernization."
    ),
    RoadmapPhaseName.MODERNIZE: (
        "Address structural, dependency, and platform modernization recommendations."
    ),
    RoadmapPhaseName.OPTIMIZE: (
        "Improve performance and operational efficiency after core modernization."
    ),
}

PHASE_OUTCOMES: dict[RoadmapPhaseName, str] = {
    RoadmapPhaseName.STABILIZE: (
        "Foundational build, test, documentation, and governance gaps are addressed."
    ),
    RoadmapPhaseName.SECURE: (
        "Identified security hygiene recommendations are remediated or explicitly deferred."
    ),
    RoadmapPhaseName.MODERNIZE: (
        "Architecture, dependency, and modernization recommendations progress under control."
    ),
    RoadmapPhaseName.OPTIMIZE: (
        "Performance-oriented recommendations are executed after earlier phases."
    ),
}
