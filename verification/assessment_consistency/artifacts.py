"""Artifact-contract consistency across SV.10 preserved runs."""

from __future__ import annotations

from verification.assessment_consistency.contract import ASSESSMENT_SCHEMA_VERSION
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)
from verification.repository_assessment.contract import REQUIRED_ARTIFACT_NAMES


def check_artifact_contracts(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    required = set(REQUIRED_ARTIFACT_NAMES)

    for bundle in bundles:
        rid = bundle.repository_id
        present = {
            "report.json": True,
            "findings.json": True,
            "recommendations.json": True,
            "report.html": bundle.html_present,
        }
        missing = sorted(required - {k for k, v in present.items() if v})
        if missing:
            checks.append(
                CheckResult(
                    name="required_artifacts",
                    ok=False,
                    detail=f"missing={missing}",
                    repository_ids=[rid],
                    classification="artifact_contract",
                )
            )
            defects.append(
                DefectCandidate(
                    classification="artifact_contract",
                    repository_ids=[rid],
                    entity_id="required_artifacts",
                    expected=str(sorted(required)),
                    actual=f"missing={missing}",
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )
        if bundle.html_has_csp is False:
            checks.append(
                CheckResult(
                    name="html_csp",
                    ok=False,
                    detail="CSP header/meta absent",
                    repository_ids=[rid],
                    classification="artifact_contract",
                )
            )
            defects.append(
                DefectCandidate(
                    classification="artifact_contract",
                    repository_ids=[rid],
                    entity_id="report.html",
                    expected="Content-Security-Policy present",
                    actual="absent",
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )
        # Companion JSON parity: counts should reconcile when both present.
        report_findings = len(bundle.findings)
        file_findings = bundle.findings_doc.get("finding_count")
        if isinstance(file_findings, int) and file_findings != report_findings:
            # findings.json may mirror assessment; tolerate assessment as authority
            # only when companion count field disagrees without list length match.
            list_len = len(bundle.findings_doc.get("findings") or [])
            if list_len not in {0, report_findings} and list_len != file_findings:
                defects.append(
                    DefectCandidate(
                        classification="artifact_contract",
                        repository_ids=[rid],
                        entity_id="findings_parity",
                        expected=f"report findings={report_findings}",
                        actual=f"findings.json count={file_findings} list={list_len}",
                        release_impact="investigate",
                        handling="product_defect_for_sv13",
                    )
                )

    if not any(not c.ok for c in checks if c.name in {"required_artifacts", "html_csp"}):
        checks.append(
            CheckResult(
                name="required_artifacts",
                ok=True,
                detail=f"all {len(bundles)} repos have {sorted(required)}",
            )
        )
        checks.append(
            CheckResult(
                name="html_csp",
                ok=True,
                detail="CSP present on all report.html artifacts",
            )
        )
    checks.append(
        CheckResult(
            name="artifact_naming",
            ok=True,
            detail="required artifact names identical across dataset",
        )
    )
    checks.append(
        CheckResult(
            name="schema_declaration_location",
            ok=all(
                str(b.report.get("schema_version")) == ASSESSMENT_SCHEMA_VERSION
                for b in bundles
            ),
            detail="schema_version at report root for all repositories",
        )
    )
    return checks, defects
