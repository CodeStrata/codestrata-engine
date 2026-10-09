"""Validate launch-catalog evidence before FAIL is admitted."""

from __future__ import annotations

from codestrata.domain.contracts.serialization import (
    walk_forbidden_credentials,
    walk_forbidden_identity,
)
from codestrata.domain.rules.errors import RuleEvidenceError
from codestrata.domain.rules.execution_models import LaunchEvidence


def validate_launch_evidence(
    items: tuple[LaunchEvidence, ...] | list[LaunchEvidence],
) -> tuple[LaunchEvidence, ...]:
    def evidence_key(item: LaunchEvidence) -> tuple[str, str, str]:
        return (item.subject_id, item.source_kind, item.relative_path or "")

    ordered = tuple(sorted(items, key=evidence_key))
    unique: list[LaunchEvidence] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in ordered:
        key = (item.subject_id, item.source_kind, item.relative_path)
        if key in seen:
            continue
        seen.add(key)
        payload = item.model_dump(mode="json")
        try:
            walk_forbidden_identity(payload)
            walk_forbidden_credentials(payload)
        except ValueError as error:
            raise RuleEvidenceError(str(error), reason_code="forbidden_evidence") from error
        if not item.schema_name or not item.schema_version:
            raise RuleEvidenceError(
                "evidence schema is required",
                reason_code="missing_evidence_schema",
            )
        unique.append(item)
    return tuple(unique)


def evidence_from_operator_members(
    members: tuple[str, ...],
    *,
    source_kind: str,
    extractor_version: str,
    relative_paths: dict[str, str] | None = None,
) -> tuple[LaunchEvidence, ...]:
    paths = relative_paths or {}
    items: list[LaunchEvidence] = []
    for member in members:
        items.append(
            LaunchEvidence(
                subject_id=member,
                source_kind=source_kind,
                relative_path=paths.get(member),
                extractor_version=extractor_version,
            )
        )
    return validate_launch_evidence(tuple(items))
