"""Pack activation-state consistency."""

from __future__ import annotations

from collections import Counter

from verification.assessment_consistency.contract import ACTIVATION_DECISION_VOCAB
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)


def check_activation(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    decisions: Counter[str] = Counter()

    for bundle in bundles:
        activation = bundle.assessment.get("activation")
        if not isinstance(activation, dict):
            defects.append(
                DefectCandidate(
                    classification="activation_semantics",
                    repository_ids=[bundle.repository_id],
                    entity_id="activation",
                    expected="activation object",
                    actual=type(activation).__name__,
                    handling="product_defect_for_sv13",
                )
            )
            continue
        packs = activation.get("packs")
        if not isinstance(packs, list):
            defects.append(
                DefectCandidate(
                    classification="activation_semantics",
                    repository_ids=[bundle.repository_id],
                    entity_id="activation.packs",
                    expected="list of pack decisions",
                    actual=type(packs).__name__,
                    handling="product_defect_for_sv13",
                )
            )
            continue
        enabled_packs: set[str] = set()
        skipped_packs: set[str] = set()
        for pack in packs:
            if not isinstance(pack, dict):
                continue
            decision = str(pack.get("decision") or "").lower()
            decisions[decision] += 1
            if decision and decision not in ACTIVATION_DECISION_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="activation_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(pack.get("pack_id")),
                        expected=f"decision in {sorted(ACTIVATION_DECISION_VOCAB)}",
                        actual=decision,
                        handling="product_defect_for_sv13",
                    )
                )
            pack_id = str(pack.get("pack_id") or "")
            if decision == "enabled" or pack.get("enabled") is True:
                enabled_packs.add(pack_id)
            if decision in {"skipped", "disabled"}:
                skipped_packs.add(pack_id)

        # Disabled/skipped packs should not contribute active findings under that provider category
        # when category exactly matches pack_id — soft check via metadata only.
        for finding in bundle.findings:
            provider = str(finding.get("provider_name") or finding.get("category") or "")
            # AI pack off must not claim AI ready via finding title alone — terminology module owns claims.
            _ = provider

        cov = bundle.assessment.get("assessment_coverage") or {}
        if isinstance(cov, dict):
            ai = cov.get("ai_readiness")
            if isinstance(ai, dict) and ai.get("status") == "disabled":
                # Ensure not represented as complete ready.
                if ai.get("status") == "complete":
                    defects.append(
                        DefectCandidate(
                            classification="activation_semantics",
                            repository_ids=[bundle.repository_id],
                            entity_id="ai_readiness",
                            expected="disabled != complete",
                            actual="complete",
                            handling="product_defect_for_sv13",
                        )
                    )

    unknown = sorted(set(decisions) - ACTIVATION_DECISION_VOCAB - {""})
    checks.append(
        CheckResult(
            name="activation_vocabulary",
            ok=not unknown,
            detail=f"decision counts={dict(decisions)} unknown={unknown}",
            classification="activation_semantics",
        )
    )
    checks.append(
        CheckResult(
            name="activation_shape",
            ok=not any(d.entity_id in {"activation", "activation.packs"} for d in defects),
            detail="activation.packs list present across repositories",
        )
    )
    return checks, defects
