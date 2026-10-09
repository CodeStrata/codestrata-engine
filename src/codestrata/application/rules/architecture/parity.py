"""Parity from retained Python architecture rules to launch YAML identities.

score_equivalent is always false. A matching count is not an old health score.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)

PARITY_VERSION = "e07.3.v1"


class RuleParity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    python_rule_id: str
    yaml_rule_id: str
    measurement_ids: tuple[str, ...]
    score_equivalent: bool
    non_equivalence: str
    default_severity: str
    default_parameters: dict[str, str]

    @field_validator("score_equivalent")
    @classmethod
    def refuse_score_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("architecture parity must not claim score equivalence")
        return value


class NotRetainedRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    python_rule_id: str
    reason: str


ARCHITECTURE_PARITY: tuple[RuleParity, ...] = (
    RuleParity(
        python_rule_id=RULE_DEPENDENCY_CYCLE,
        yaml_rule_id="architecture.cycles",
        measurement_ids=("M05",),
        score_equivalent=False,
        non_equivalence=(
            "The Python rule skips composition-root cycles and raises severity with "
            "cycle size. YAML counts each SCC of size greater than 1 plus each "
            "self-loop once, and FAILs at medium when that count is above zero."
        ),
        default_severity="medium",
        default_parameters={"max_cycle_length": "8"},
    ),
    RuleParity(
        python_rule_id=RULE_INVALID_DEPENDENCY_DIRECTION,
        yaml_rule_id="architecture.invalid-dependency-direction",
        measurement_ids=("M07",),
        score_equivalent=False,
        non_equivalence=(
            "The Python rule applies conventional layer coverage and skips "
            "composition roots. YAML FAILs only against an explicit allowed-direction "
            "set supplied for the run. Same-layer edges are allowed. No Python count "
            "is copied forward as a score."
        ),
        default_severity="medium",
        default_parameters={"violation_bound": "0"},
    ),
    RuleParity(
        python_rule_id=RULE_LAYER_BOUNDARY_VIOLATION,
        yaml_rule_id="architecture.boundary",
        measurement_ids=("M07",),
        score_equivalent=False,
        non_equivalence=(
            "The Python rule hard-codes presentation and API skips into persistence "
            "or infrastructure. YAML counts unique edges against an explicit local "
            "pattern. The bundled API-to-internal example is direct depth 1 and does "
            "not apply unless the run declares that pattern."
        ),
        default_severity="high",
        default_parameters={"constraint_id": "forbid:api->internal", "max_depth": "1"},
    ),
    RuleParity(
        python_rule_id=RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
        yaml_rule_id="architecture.fan-out",
        measurement_ids=("M06",),
        score_equivalent=False,
        non_equivalence=(
            "The Python rule uses absolute threshold 8, a peer-median multiplier, "
            "and a minimum of five modules. YAML threshold is 10 distinct modules. "
            "Unresolved imports are a lower bound and cannot PASS."
        ),
        default_severity="medium",
        default_parameters={"max_fan_out": "10"},
    ),
    RuleParity(
        python_rule_id=RULE_COMPONENT_CONCENTRATION,
        yaml_rule_id="architecture.concentration",
        measurement_ids=("M08",),
        score_equivalent=False,
        non_equivalence=(
            "The Python rule uses incident-edge share 0.30 among at least five "
            "modules. YAML uses nonblank noncomment line share 0.60 with at least "
            "two components and is advisory. The shares are not interchangeable."
        ),
        default_severity="low",
        default_parameters={"max_share": "0.60"},
    ),
    RuleParity(
        python_rule_id=RULE_FRAMEWORK_LEAKAGE,
        yaml_rule_id="architecture.framework-leakage",
        measurement_ids=(),
        score_equivalent=False,
        non_equivalence=(
            "The Python rule matches framework symbols on the legacy architecture "
            "view. YAML counts structural framework hits only. A detection-only or "
            "non-structural tier cannot PASS. Hit counts are not a health score."
        ),
        default_severity="medium",
        default_parameters={"violation_bound": "0"},
    ),
)

NOT_RETAINED_ARCHITECTURE_RULES: tuple[NotRetainedRule, ...] = (
    NotRetainedRule(
        python_rule_id=RULE_ENTERPRISE_STANDARD_MISMATCH,
        reason=(
            "Not in the E01.1 retained launch rule ids. Enterprise context is not "
            "invented by Engine, so this rule is not a launch YAML check."
        ),
    ),
    NotRetainedRule(
        python_rule_id="architecture.service-dependency-cycle",
        reason=(
            "Deferred. A distinct service graph is not available from the repository "
            "graph, so the rule is not migrated."
        ),
    ),
)


def parity_by_yaml_id() -> dict[str, RuleParity]:
    return {item.yaml_rule_id: item for item in ARCHITECTURE_PARITY}


__all__ = [
    "ARCHITECTURE_PARITY",
    "NOT_RETAINED_ARCHITECTURE_RULES",
    "PARITY_VERSION",
    "NotRetainedRule",
    "RuleParity",
    "parity_by_yaml_id",
]
