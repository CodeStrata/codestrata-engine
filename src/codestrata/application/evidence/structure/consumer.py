"""Consumer check for architecture comparison projections.

Validates schema, the four result statuses, declared language tiers and the
absence of a health score. Does not recompute graph metrics or import the
Python SharedRule implementations.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from codestrata.application.evidence.structure.projection import (
    COMPARISON_SCHEMA,
    ArchitectureComparison,
)

FOUR_OUTCOMES = frozenset({"pass", "fail", "unknown", "not_applicable"})
ALLOWED_STATUSES = FOUR_OUTCOMES | {"error"}
FORBIDDEN_SCORE_KEYS = frozenset(
    {
        "health_score",
        "overall_score",
        "architecture_score",
        "quality_score",
        "maintainability_index",
        "old_to_new_score",
        "equivalent_score",
    }
)
DEEPEST = frozenset({"java", "javascript", "typescript"})
RETAINED = frozenset({"python", "php", "csharp"})


class ConsumerContractError(ValueError):
    """Projection failed the architecture consumer contract."""


def _walk_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_SCORE_KEYS:
                raise ConsumerContractError(f"invented score field at {path}.{key_text}")
            _walk_forbidden(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk_forbidden(item, path=f"{path}[{index}]")


def consume_architecture_projection(payload: object) -> ArchitectureComparison:
    if not isinstance(payload, dict):
        raise ConsumerContractError("architecture projection must be an object")
    _walk_forbidden(payload)
    try:
        projection = ArchitectureComparison.model_validate(payload)
    except ValidationError as error:
        raise ConsumerContractError("corrupt architecture projection") from error
    if projection.schema_name != COMPARISON_SCHEMA:
        raise ConsumerContractError("unexpected architecture projection schema")
    if projection.score_equivalent:
        raise ConsumerContractError("old-to-new score equivalence is not claimed")
    if projection.health_verdict != "none":
        raise ConsumerContractError("architecture projection has no health verdict")
    if projection.old_score is not None:
        raise ConsumerContractError("old score must stay unset")
    if not projection.parity:
        raise ConsumerContractError("parity map is empty")
    for row in projection.parity:
        if row.score_equivalent:
            raise ConsumerContractError(f"{row.python_rule_id} claims score equivalence")
    expected_coverage = {
        "pass": "complete",
        "fail": "complete",
        "unknown": "unknown",
        "not_applicable": "not_applicable",
        "error": "error",
    }
    yaml_ids = {item.yaml_rule_id for item in projection.parity}
    for record in projection.records:
        if record.status not in ALLOWED_STATUSES:
            raise ConsumerContractError(f"unsupported status {record.status}")
        if record.rule_id not in yaml_ids:
            raise ConsumerContractError(f"record {record.rule_id} is outside the parity map")
        if record.coverage_state != expected_coverage[record.status]:
            raise ConsumerContractError(
                f"{record.rule_id} coverage {record.coverage_state} does not match {record.status}"
            )
    tiers = {item.language: item for item in projection.language_tiers}
    for language in DEEPEST:
        tier = tiers.get(language)
        if tier is None or tier.launch_tier != "deepest_target":
            raise ConsumerContractError(f"{language} must stay a deepest target")
    for language in RETAINED:
        tier = tiers.get(language)
        if tier is None or tier.launch_tier != "verified_retained":
            raise ConsumerContractError(f"{language} must stay on the verified retained tier")
        if tier.structural_maturity == "mature":
            raise ConsumerContractError(f"{language} was promoted past its declared tier")
    typescript = tiers["typescript"]
    javascript = tiers["javascript"]
    if typescript.provider_id != javascript.provider_id:
        raise ConsumerContractError("TypeScript must stay on the JavaScript provider")
    if projection.graph.centrality_status != "descriptive":
        raise ConsumerContractError("centrality is descriptive and has no verdict")
    if "health_verdict: none" not in projection.launch_html:
        raise ConsumerContractError("HTML projection dropped the empty health verdict")
    _walk_forbidden(projection.launch_json)
    _walk_forbidden(projection.launch_sarif)
    return projection


__all__ = [
    "ALLOWED_STATUSES",
    "ConsumerContractError",
    "FOUR_OUTCOMES",
    "consume_architecture_projection",
]
