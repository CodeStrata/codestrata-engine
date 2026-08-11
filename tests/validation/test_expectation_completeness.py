"""Slice 4.13 — expectation completeness across active set."""

from __future__ import annotations

from validation.matrix import ACTIVE_VALIDATION_SET
from validation.registry import load_all_repositories, resolve_expected_results

PACK_FIELDS = (
    "technology_inventory",
    "security",
    "architecture",
    "technical_debt",
    "dependency",
    "cloud",
    "ai_readiness",
    "modernization",
)


def test_every_active_expectation_has_all_eight_packs() -> None:
    definitions = {item.repository_id: item for item in load_all_repositories()}
    for repository_id in ACTIVE_VALIDATION_SET:
        expected = resolve_expected_results(definitions[repository_id])
        assert expected.schema_version == "1.2", repository_id
        assert expected.expect_ai_executed is False, repository_id
        for field in PACK_FIELDS:
            block = getattr(expected, field)
            assert block is not None, (repository_id, field)


def test_every_pack_has_evidence_notes() -> None:
    definitions = {item.repository_id: item for item in load_all_repositories()}
    for repository_id in ACTIVE_VALIDATION_SET:
        expected = resolve_expected_results(definitions[repository_id])
        for field in PACK_FIELDS:
            block = getattr(expected, field)
            assert block is not None
            assert block.evidence_notes.strip(), (repository_id, field)
