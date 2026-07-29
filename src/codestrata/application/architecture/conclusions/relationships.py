"""Build deterministic relationships among architecture findings."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.architecture.conclusions.rule_catalog import (
    BOUNDARY_RULES,
    COUPLING_RULES,
    catalog_entry,
)
from codestrata.domain.architecture.conclusions.enums import FindingRelationshipType
from codestrata.domain.architecture.conclusions.relationships import FindingRelationship
from codestrata.domain.findings import Finding
from codestrata.domain.rules.enums import RuleConfidence


def _subject_keys(finding: Finding) -> frozenset[str]:
    raw = finding.metadata.get("subject_keys")
    if isinstance(raw, (list, tuple)):
        return frozenset(str(item).lower() for item in raw if str(item).strip())
    if isinstance(raw, str) and raw.strip():
        return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())
    return frozenset()


def _scope_tokens(finding: Finding) -> frozenset[str]:
    subjects = _subject_keys(finding)
    # Drop generic markers.
    noise = {"cycle", "out", "application", "infrastructure", "domain", "presentation"}
    return frozenset(token for token in subjects if token not in noise and ":" not in token)


def build_finding_relationships(
    findings: Sequence[Finding],
) -> tuple[FindingRelationship, ...]:
    architecture = [
        finding
        for finding in findings
        if finding.rule_id.startswith("architecture.")
    ]
    ordered = sorted(architecture, key=lambda item: (item.rule_id, item.id))
    relationships: list[FindingRelationship] = []

    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            catalog = catalog_entry(left.rule_id, right.rule_id)
            if catalog is None:
                continue
            rel_type, reason = catalog
            left_scope = _scope_tokens(left)
            right_scope = _scope_tokens(right)
            shared = left_scope.intersection(right_scope)

            # Option A: do not cluster coupling into boundary-integrity unless
            # scopes clearly overlap on the same architectural units.
            left_boundary = left.rule_id in BOUNDARY_RULES
            right_boundary = right.rule_id in BOUNDARY_RULES
            left_coupling = left.rule_id in COUPLING_RULES
            right_coupling = right.rule_id in COUPLING_RULES
            if (left_boundary and right_coupling) or (right_boundary and left_coupling):
                if not shared:
                    continue
                # Coupling reinforcing a cycle/direction only when unit shared.
                rel_type = FindingRelationshipType.SUPPORTS
                reason = "coupled_unit_also_in_boundary_concern"
                confidence = RuleConfidence.LOW
            else:
                confidence = RuleConfidence.HIGH if shared else RuleConfidence.MEDIUM
                if not shared and rel_type is FindingRelationshipType.OVERLAPS:
                    # Overlaps require shared dependency scope.
                    continue
                if (
                    not shared
                    and reason == "cycle_and_direction_same_boundary"
                ):
                    # Still relate if both mention same pair via subject intersection
                    # of any non-noise tokens; otherwise skip.
                    continue

            # For cycle + direction, require shared architectural units.
            if reason == "cycle_and_direction_same_boundary" and not shared:
                continue

            supporting = ",".join(sorted(shared)) if shared else None
            relationships.append(
                FindingRelationship(
                    relationship_type=rel_type,
                    source_finding_id=left.id,
                    target_finding_id=right.id,
                    reason_code=reason,
                    supporting_subject=supporting,
                    confidence=confidence,
                )
            )

    return tuple(
        sorted(
            relationships,
            key=lambda item: (
                item.source_finding_id,
                item.target_finding_id,
                item.reason_code,
            ),
        )
    )
