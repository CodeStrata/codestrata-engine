"""Repository limitation placement consistency."""

from __future__ import annotations

from verification.assessment_consistency.contract import EXPECTED_LIMITATION_REPOS
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)


def check_limitations(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []

    by_id = {b.repository_id: b for b in bundles}

    for rid, needles in EXPECTED_LIMITATION_REPOS.items():
        bundle = by_id.get(rid)
        if bundle is None:
            defects.append(
                DefectCandidate(
                    classification="limitation_placement",
                    repository_ids=[rid],
                    entity_id="missing_repository",
                    expected="SV.10 limitation repository present",
                    actual="absent",
                    handling="verification_harness_fix",
                )
            )
            continue
        text = " ".join(str(x).lower() for x in (bundle.record.get("limitations") or []))
        if not any(n in text for n in needles):
            defects.append(
                DefectCandidate(
                    classification="limitation_placement",
                    repository_ids=[rid],
                    entity_id="expected_limitation",
                    expected=f"limitation mentioning one of {needles}",
                    actual=text[:200] or "empty",
                    handling="verification_harness_fix",
                )
            )
        # Limitation must not flip assessment_result semantics to invent failure.
        if bundle.record.get("assessment_result") not in {"pass", "PASS"}:
            # Still allow PASS_WITH_LIMITATIONS verdict with pass assessment.
            if bundle.record.get("verdict") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
                defects.append(
                    DefectCandidate(
                        classification="limitation_placement",
                        repository_ids=[rid],
                        entity_id="assessment_semantics",
                        expected="limitation does not invent silent skip/failure without classification",
                        actual=str(bundle.record.get("verdict")),
                        handling="documentation_only",
                    )
                )

    # Submodule limitations must not appear on unrelated repos.
    for bundle in bundles:
        text = " ".join(str(x).lower() for x in (bundle.record.get("limitations") or []))
        if "submodule" in text and bundle.repository_id not in {"aspnetcore", "doris"}:
            defects.append(
                DefectCandidate(
                    classification="limitation_placement",
                    repository_ids=[bundle.repository_id],
                    entity_id="submodule_limitation",
                    expected="submodule limitation only on aspnetcore/doris",
                    actual="present",
                    handling="verification_harness_fix",
                )
            )
        if ("secret-shaped" in text or "known issues" in text) and bundle.repository_id not in {
            "juice-shop",
            "nodegoat",
        }:
            # Soft: other repos may have similar notes; only flag explicit Known Issues wording bleed.
            if "intentionally contains secret-shaped" in text:
                defects.append(
                    DefectCandidate(
                        classification="limitation_placement",
                        repository_ids=[bundle.repository_id],
                        entity_id="known_issues_limitation",
                        expected="Known Issues limitation scoped to juice-shop/nodegoat",
                        actual="present",
                        handling="verification_harness_fix",
                    )
                )

    checks.append(
        CheckResult(
            name="sv10_limitations_scoped",
            ok=not any(d.classification == "limitation_placement" for d in defects),
            detail="Known Issues / BookStack / submodule limitations correctly scoped",
        )
    )
    return checks, defects
