"""Tests for ``capability_compatibility`` statements and prior-slice notes."""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_compatibility import (
    build_capability_compatibility_statements,
    build_prior_slice_compatibility_notes,
)
from codestrata.ai.provider_contracts.capability_policy import (
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)


def test_statements_cover_exactly_the_required_requirement_ids() -> None:
    statements = build_capability_compatibility_statements()
    ids = tuple(sorted(s.requirement_id for s in statements))
    assert ids == tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))


def test_every_statement_holds_true() -> None:
    statements = build_capability_compatibility_statements()
    assert all(s.holds for s in statements)


def test_every_statement_has_a_non_empty_explanation() -> None:
    statements = build_capability_compatibility_statements()
    assert all(s.explanation.strip() for s in statements)


def test_prior_slice_notes_cover_11_2_11_3_and_11_4() -> None:
    notes = build_prior_slice_compatibility_notes()
    ids = tuple(sorted(n.slice_id for n in notes))
    assert ids == ("11.2", "11.3", "11.4")


def test_every_prior_slice_note_holds_true() -> None:
    notes = build_prior_slice_compatibility_notes()
    assert all(n.holds for n in notes)


def test_every_prior_slice_note_has_a_non_empty_explanation() -> None:
    notes = build_prior_slice_compatibility_notes()
    assert all(n.explanation.strip() for n in notes)
