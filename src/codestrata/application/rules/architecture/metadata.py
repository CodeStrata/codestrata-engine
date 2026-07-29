"""Executive interpretation and taxonomy metadata for architecture rules."""

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

# taxonomy_id -> Assessment Framework rule taxonomy leaf
RULE_TAXONOMY: dict[str, str] = {
    RULE_DEPENDENCY_CYCLE: "architecture.dependency-structure",
    RULE_INVALID_DEPENDENCY_DIRECTION: "architecture.layering",
    RULE_LAYER_BOUNDARY_VIOLATION: "architecture.boundaries",
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING: "architecture.coupling",
    RULE_COMPONENT_CONCENTRATION: "architecture.modularity",
    RULE_FRAMEWORK_LEAKAGE: "architecture.boundaries",
    RULE_ENTERPRISE_STANDARD_MISMATCH: "architecture.enterprise-standards",
}

RULE_DIMENSIONS: dict[str, tuple[str, ...]] = {
    RULE_DEPENDENCY_CYCLE: ("architecture", "maintainability", "modernization_readiness"),
    RULE_INVALID_DEPENDENCY_DIRECTION: ("architecture", "maintainability"),
    RULE_LAYER_BOUNDARY_VIOLATION: ("architecture", "maintainability", "security_posture"),
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING: ("architecture", "maintainability"),
    RULE_COMPONENT_CONCENTRATION: ("architecture", "modernization_readiness"),
    RULE_FRAMEWORK_LEAKAGE: ("architecture", "maintainability", "modernization_readiness"),
    RULE_ENTERPRISE_STANDARD_MISMATCH: ("architecture", "governance"),
}

RULE_EXECUTIVE: dict[str, dict[str, str]] = {
    RULE_DEPENDENCY_CYCLE: {
        "executive_concern": "Change risk and modernization complexity.",
        "engineering_consequence": (
            "Changes in one component may require coordinated changes across the cycle."
        ),
        "modernization_relevance": (
            "Cycles should be addressed before modular extraction or service decomposition."
        ),
        "narrative_key": "architecture.dependency_cycle",
        "report_sections": "Material Risks;Architecture Assessment;Modernization Readiness",
        "leadership_question": "Where do circular dependencies increase delivery risk?",
    },
    RULE_INVALID_DEPENDENCY_DIRECTION: {
        "executive_concern": "Architectural layering discipline.",
        "engineering_consequence": "Inner layers depending on outer layers increase churn.",
        "modernization_relevance": "Layering must be restored before platform extraction.",
        "narrative_key": "architecture.invalid_dependency_direction",
        "report_sections": "Architecture Assessment;Recommended Modernization Roadmap",
        "leadership_question": "Are architectural dependency directions being respected?",
    },
    RULE_LAYER_BOUNDARY_VIOLATION: {
        "executive_concern": "Boundary integrity and change isolation.",
        "engineering_consequence": "Skipped intermediaries couple UI/API directly to persistence.",
        "modernization_relevance": "Boundary skips block safe service and module extraction.",
        "narrative_key": "architecture.layer_boundary_violation",
        "report_sections": "Material Risks;Architecture Assessment",
        "leadership_question": "Where do components bypass required architectural boundaries?",
    },
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING: {
        "executive_concern": "Coordination cost across modules.",
        "engineering_consequence": (
            "Broad dependency surfaces may increase change coordination effort."
        ),
        "modernization_relevance": "High fan-out modules are harder to extract cleanly.",
        "narrative_key": "architecture.excessive_cross_module_coupling",
        "report_sections": "Architecture Assessment;Modernization Readiness",
        "leadership_question": "Which modules concentrate outward dependency risk?",
    },
    RULE_COMPONENT_CONCENTRATION: {
        "executive_concern": "Architectural bottleneck risk.",
        "engineering_consequence": (
            "Concentrated connectivity may create change and ownership bottlenecks."
        ),
        "modernization_relevance": "Bottleneck components complicate decomposition planning.",
        "narrative_key": "architecture.component_concentration",
        "report_sections": "Architecture Assessment;Material Risks",
        "leadership_question": "Which components concentrate graph connectivity?",
    },
    RULE_FRAMEWORK_LEAKAGE: {
        "executive_concern": "Framework lock-in within core domains.",
        "engineering_consequence": "Framework types in domain boundaries impede portability.",
        "modernization_relevance": "Leakage should be reduced before platform migration.",
        "narrative_key": "architecture.framework_leakage",
        "report_sections": "Architecture Assessment;Modernization Readiness",
        "leadership_question": "Is core business logic independent of frameworks?",
    },
    RULE_ENTERPRISE_STANDARD_MISMATCH: {
        "executive_concern": "Alignment to declared enterprise architecture standards.",
        "engineering_consequence": "Observed architecture diverges from governed standards.",
        "modernization_relevance": "Standards gaps should be resolved or formally excepted.",
        "narrative_key": "architecture.enterprise_standard_mismatch",
        "report_sections": "Governance;Architecture Assessment;Material Risks",
        "leadership_question": "Where do repositories diverge from enterprise standards?",
    },
}


def taxonomy_for(rule_id: str) -> str:
    return RULE_TAXONOMY.get(rule_id, "architecture.dependency-structure")


def dimensions_for(rule_id: str) -> tuple[str, ...]:
    return RULE_DIMENSIONS.get(rule_id, ("architecture",))


def executive_for(rule_id: str) -> dict[str, str]:
    return dict(RULE_EXECUTIVE.get(rule_id, {}))
