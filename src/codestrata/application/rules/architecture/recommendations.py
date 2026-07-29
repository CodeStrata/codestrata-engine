"""Recommendation templates for Architecture Intelligence findings."""

from __future__ import annotations

from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)

# effort bands: small | medium | large | program | unknown
RECOMMENDATIONS: dict[str, dict[str, str]] = {
    RULE_DEPENDENCY_CYCLE: {
        "action": (
            "Break the cycle using dependency inversion, a stable abstraction, "
            "responsibility realignment, interface extraction, an event boundary, "
            "or a shared neutral module."
        ),
        "rationale": "Directed cycles force coordinated multi-component changes.",
        "expected_outcome": "Acyclic package dependencies within the affected scope.",
        "effort_band": "medium",
        "validation": (
            "Regenerate the package dependency graph and confirm the cycle identity "
            "is absent."
        ),
    },
    RULE_INVALID_DEPENDENCY_DIRECTION: {
        "action": (
            "Redirect the dependency toward the allowed inward direction, or move "
            "shared types behind an approved boundary interface."
        ),
        "rationale": "Wrong-direction dependencies invert architectural control.",
        "expected_outcome": "Dependencies conform to the declared layer direction model.",
        "effort_band": "medium",
        "validation": "Re-run layer direction analysis; prohibited edges should be gone.",
    },
    RULE_LAYER_BOUNDARY_VIOLATION: {
        "action": (
            "Route access through the expected application/domain boundary instead of "
            "reaching persistence or infrastructure directly from presentation/API layers."
        ),
        "rationale": "Boundary skips couple distant layers and enlarge blast radius.",
        "expected_outcome": "Presentation/API no longer depend directly on persistence.",
        "effort_band": "medium",
        "validation": "Confirm presentation→persistence edges are removed from the graph.",
    },
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING: {
        "action": (
            "Reduce outward dependencies by extracting shared abstractions, splitting "
            "responsibilities, or introducing a narrower facade."
        ),
        "rationale": (
            "A broad dependency surface may increase change coordination and make "
            "architectural boundaries harder to maintain."
        ),
        "expected_outcome": "Outgoing unique module dependencies fall below the threshold.",
        "effort_band": "large",
        "validation": "Recount outgoing module edges after the refactor.",
    },
    RULE_COMPONENT_CONCENTRATION: {
        "action": (
            "Redistribute responsibilities or extract collaborators so connectivity "
            "is less concentrated in a single architectural unit."
        ),
        "rationale": "Concentrated connectivity can create architectural bottlenecks.",
        "expected_outcome": "Incident edge share falls below the configured threshold.",
        "effort_band": "large",
        "validation": "Recompute incident edge share for the affected unit.",
    },
    RULE_FRAMEWORK_LEAKAGE: {
        "action": (
            "Move framework annotations and SDK types behind adapters; keep domain "
            "contracts free of persistence and web-framework symbols."
        ),
        "rationale": "Framework leakage reduces portability of core domain boundaries.",
        "expected_outcome": "Domain-classified units no longer reference framework symbols.",
        "effort_band": "medium",
        "validation": "Re-scan domain units for framework pattern matches.",
    },
    RULE_ENTERPRISE_STANDARD_MISMATCH: {
        "action": (
            "Align the repository with the cited enterprise standard, or update the "
            "declared standard through governance if the exception is intentional."
        ),
        "rationale": "Declared enterprise standards must be explicitly satisfied or excepted.",
        "expected_outcome": "Observed architecture matches the governing standard citation.",
        "effort_band": "program",
        "validation": "Re-evaluate with the same enterprise standard version.",
    },
}


def recommendation_for(rule_id: str) -> dict[str, str]:
    return dict(RECOMMENDATIONS.get(rule_id, {}))
