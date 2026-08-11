"""Cross-check capability/usage compatibility statements against the real baseline and prior slices.

This is the one place in the whole Slice 11.5 deliverable that imports
``verification.ai_provider_baseline`` — the verification tree is allowed to
depend on another verification package; the new *production* package
(``codestrata.ai.provider_contracts``) never does (see
``dependency_boundary.py``).
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capability_compatibility import (
    build_capability_compatibility_statements,
    build_prior_slice_compatibility_notes,
)
from verification.ai_provider_baseline.reporting import build_compatibility_requirements
from verification.ai_provider_capabilities.contract import (
    PRIOR_SLICE_IDS,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from verification.ai_provider_capabilities.models import CheckResult


def check_baseline_defines_exactly_six_requirements() -> CheckResult:
    requirements = build_compatibility_requirements()
    ids = tuple(r.requirement_id for r in requirements)
    ok = ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    return CheckResult(
        name="slice_11_1_baseline_defines_cr1_through_cr6",
        category="compatibility",
        ok=ok,
        detail=f"ids={ids}",
    )


def check_capability_statements_cover_every_baseline_requirement() -> CheckResult:
    requirements = build_compatibility_requirements()
    baseline_ids = {r.requirement_id for r in requirements}
    statements = build_capability_compatibility_statements()
    statement_ids = {s.requirement_id for s in statements}
    ok = baseline_ids == statement_ids
    return CheckResult(
        name="capability_compatibility_statements_cover_every_baseline_requirement",
        category="compatibility",
        ok=ok,
        detail=f"baseline_ids={sorted(baseline_ids)} statement_ids={sorted(statement_ids)}",
    )


def check_every_capability_compatibility_statement_holds() -> CheckResult:
    statements = build_capability_compatibility_statements()
    failing = [s.requirement_id for s in statements if not s.holds]
    ok = not failing
    return CheckResult(
        name="every_capability_compatibility_statement_holds_true",
        category="compatibility",
        ok=ok,
        detail=f"failing={failing}",
    )


def check_prior_slice_notes_cover_11_2_11_3_and_11_4() -> CheckResult:
    notes = build_prior_slice_compatibility_notes()
    note_ids = tuple(sorted(n.slice_id for n in notes))
    ok = note_ids == tuple(sorted(PRIOR_SLICE_IDS))
    return CheckResult(
        name="prior_slice_compatibility_notes_cover_slices_11_2_11_3_and_11_4",
        category="compatibility",
        ok=ok,
        detail=f"note_ids={note_ids} expected={tuple(sorted(PRIOR_SLICE_IDS))}",
    )


def check_every_prior_slice_compatibility_note_holds() -> CheckResult:
    notes = build_prior_slice_compatibility_notes()
    failing = [n.slice_id for n in notes if not n.holds]
    ok = not failing
    return CheckResult(
        name="every_prior_slice_compatibility_note_holds_true",
        category="compatibility",
        ok=ok,
        detail=f"failing={failing}",
    )


def check_provider_ids_match_baseline_engine_provider_ids() -> CheckResult:
    from codestrata.ai.provider_contracts.identifiers import ProviderId
    from verification.ai_provider_baseline.contract import ENGINE_PROVIDER_IDS

    contract_ids = {p.value for p in ProviderId}
    baseline_ids = set(ENGINE_PROVIDER_IDS)
    extras = sorted(contract_ids - baseline_ids)
    ok = baseline_ids.issubset(contract_ids) and set(extras) <= {"openrouter"}
    return CheckResult(
        name="provider_id_enum_superset_of_baseline_engine_provider_ids",
        category="compatibility",
        ok=ok,
        detail=(
            f"contract_ids={sorted(contract_ids)} baseline_ids={sorted(baseline_ids)} "
            f"extras={extras}"
        ),
    )


def run_compatibility_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_baseline_defines_exactly_six_requirements(),
        check_capability_statements_cover_every_baseline_requirement(),
        check_every_capability_compatibility_statement_holds(),
        check_prior_slice_notes_cover_11_2_11_3_and_11_4(),
        check_every_prior_slice_compatibility_note_holds(),
        check_provider_ids_match_baseline_engine_provider_ids(),
    ]
    requirements = build_compatibility_requirements()
    statements = build_capability_compatibility_statements()
    notes = build_prior_slice_compatibility_notes()
    matrix = {
        "prior_slice_notes_hold_by_slice_id": {
            n.slice_id: n.holds for n in sorted(notes, key=lambda n: n.slice_id)
        },
        "requirement_ids": sorted(r.requirement_id for r in requirements),
        "statement_holds_by_requirement_id": {
            s.requirement_id: s.holds for s in sorted(statements, key=lambda s: s.requirement_id)
        },
    }
    return checks, matrix


__all__ = [
    "check_baseline_defines_exactly_six_requirements",
    "check_capability_statements_cover_every_baseline_requirement",
    "check_every_capability_compatibility_statement_holds",
    "check_every_prior_slice_compatibility_note_holds",
    "check_prior_slice_notes_cover_11_2_11_3_and_11_4",
    "check_provider_ids_match_baseline_engine_provider_ids",
    "run_compatibility_checks",
]
