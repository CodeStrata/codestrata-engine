"""Cross-check the configuration domain against the real, loaded Slice 11.1 baseline.

This is the one place in the Slice 11.3 verification suite that imports
``verification.ai_provider_baseline`` — the verification tree is allowed to
depend on another verification package; the new *production* modules
(``codestrata.ai.provider_contracts.configuration_*``) never do (see
``dependency_boundary.py``).
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.configuration_compatibility import (
    build_configuration_compatibility_statements,
)
from codestrata.ai.provider_contracts.configuration_policy import (
    DEFAULT_MODEL_BY_PROVIDER,
    DEFAULT_PROVIDER_ID,
)
from verification.ai_provider_baseline.contract import (
    DEFAULT_ASSESS_PROVIDER,
    DEFAULT_MODEL_IDS,
    ENGINE_PROVIDER_IDS,
)
from verification.ai_provider_baseline.reporting import build_compatibility_requirements
from verification.ai_provider_configuration.contract import (
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from verification.ai_provider_configuration.models import CheckResult


def check_baseline_defines_exactly_six_requirements() -> CheckResult:
    requirements = build_compatibility_requirements()
    ids = tuple(r.requirement_id for r in requirements)
    ok = ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    return CheckResult(
        name="slice_11_1_baseline_defines_cr1_through_cr6",
        category="baseline_compatibility",
        ok=ok,
        detail=f"ids={ids}",
    )


def check_configuration_statements_cover_every_baseline_requirement() -> CheckResult:
    requirements = build_compatibility_requirements()
    baseline_ids = {r.requirement_id for r in requirements}
    statements = build_configuration_compatibility_statements()
    statement_ids = {s.requirement_id for s in statements}
    ok = baseline_ids == statement_ids
    return CheckResult(
        name="configuration_compatibility_statements_cover_every_baseline_requirement",
        category="baseline_compatibility",
        ok=ok,
        detail=f"baseline_ids={sorted(baseline_ids)} statement_ids={sorted(statement_ids)}",
    )


def check_every_compatibility_statement_holds() -> CheckResult:
    statements = build_configuration_compatibility_statements()
    failing = [s.requirement_id for s in statements if not s.holds]
    ok = not failing
    return CheckResult(
        name="every_configuration_compatibility_statement_holds_true",
        category="baseline_compatibility",
        ok=ok,
        detail=f"failing={failing}",
    )


def check_default_provider_matches_baseline() -> CheckResult:
    ok = DEFAULT_PROVIDER_ID == DEFAULT_ASSESS_PROVIDER
    return CheckResult(
        name="configuration_default_provider_id_matches_baseline_default_assess_provider",
        category="baseline_compatibility",
        ok=ok,
        detail=f"configuration={DEFAULT_PROVIDER_ID!r} baseline={DEFAULT_ASSESS_PROVIDER!r}",
    )


def check_default_model_ids_match_baseline() -> CheckResult:
    ok = DEFAULT_MODEL_BY_PROVIDER == DEFAULT_MODEL_IDS
    return CheckResult(
        name="configuration_default_model_ids_match_baseline_default_model_ids",
        category="baseline_compatibility",
        ok=ok,
        detail=f"configuration={DEFAULT_MODEL_BY_PROVIDER} baseline={DEFAULT_MODEL_IDS}",
    )


def check_provider_ids_match_baseline_engine_provider_ids() -> CheckResult:
    from codestrata.ai.provider_contracts.identifiers import ProviderId

    contract_ids = {p.value for p in ProviderId}
    baseline_ids = set(ENGINE_PROVIDER_IDS)
    extras = sorted(contract_ids - baseline_ids)
    ok = baseline_ids.issubset(contract_ids) and set(extras) <= {"openrouter"}
    return CheckResult(
        name="provider_id_enum_superset_of_baseline_engine_provider_ids",
        category="baseline_compatibility",
        ok=ok,
        detail=(
            f"contract_ids={sorted(contract_ids)} baseline_ids={sorted(baseline_ids)} "
            f"extras={extras}"
        ),
    )


def run_baseline_compatibility_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_baseline_defines_exactly_six_requirements(),
        check_configuration_statements_cover_every_baseline_requirement(),
        check_every_compatibility_statement_holds(),
        check_default_provider_matches_baseline(),
        check_default_model_ids_match_baseline(),
        check_provider_ids_match_baseline_engine_provider_ids(),
    ]
    requirements = build_compatibility_requirements()
    statements = build_configuration_compatibility_statements()
    matrix = {
        "requirement_ids": sorted(r.requirement_id for r in requirements),
        "statement_holds_by_requirement_id": {
            s.requirement_id: s.holds for s in sorted(statements, key=lambda s: s.requirement_id)
        },
    }
    return checks, matrix


__all__ = [
    "check_baseline_defines_exactly_six_requirements",
    "check_configuration_statements_cover_every_baseline_requirement",
    "check_default_model_ids_match_baseline",
    "check_default_provider_matches_baseline",
    "check_every_compatibility_statement_holds",
    "check_provider_ids_match_baseline_engine_provider_ids",
    "run_baseline_compatibility_checks",
]
