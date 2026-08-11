"""Schema consistency checks for assessment reports."""

from __future__ import annotations

from verification.assessment_consistency.contract import ASSESSMENT_SCHEMA_VERSION
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)


def check_schemas(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    versions = {str(b.report.get("schema_version")) for b in bundles}
    report_versions = {str(b.report.get("report_version")) for b in bundles}

    if versions != {ASSESSMENT_SCHEMA_VERSION}:
        bad = [b.repository_id for b in bundles if str(b.report.get("schema_version")) != ASSESSMENT_SCHEMA_VERSION]
        checks.append(
            CheckResult(
                name="schema_version_uniform",
                ok=False,
                detail=f"versions={sorted(versions)}",
                repository_ids=bad,
                classification="schema_contract",
            )
        )
        defects.append(
            DefectCandidate(
                classification="schema_contract",
                repository_ids=bad,
                entity_id="schema_version",
                expected=ASSESSMENT_SCHEMA_VERSION,
                actual=str(sorted(versions)),
                release_impact="blocks_release",
                handling="product_defect_for_sv13",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="schema_version_uniform",
                ok=True,
                detail=f"all reports use schema {ASSESSMENT_SCHEMA_VERSION}",
            )
        )

    checks.append(
        CheckResult(
            name="report_version_uniform",
            ok=report_versions == {ASSESSMENT_SCHEMA_VERSION} or report_versions <= {ASSESSMENT_SCHEMA_VERSION, "None"},
            detail=f"report_version set={sorted(report_versions)}",
        )
    )

    # Boolean / numeric serialization smoke: no stringified booleans in confidence levels.
    for bundle in bundles:
        for finding in bundle.findings[:50]:
            fc = finding.get("finding_confidence")
            if isinstance(fc, dict) and isinstance(fc.get("level"), bool):
                defects.append(
                    DefectCandidate(
                        classification="schema_contract",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("id")),
                        expected="confidence level string enum",
                        actual="boolean",
                        handling="product_defect_for_sv13",
                    )
                )
        # Precision/Recall must not appear as customer validation metrics.
        blob_keys = _collect_keys(bundle.assessment)
        forbidden = {"validation_precision", "validation_recall", "precision_recall"}
        hit = sorted(forbidden & blob_keys)
        if hit:
            defects.append(
                DefectCandidate(
                    classification="schema_contract",
                    repository_ids=[bundle.repository_id],
                    entity_id="precision_recall",
                    expected="absent from customer assessment",
                    actual=str(hit),
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )

    checks.append(
        CheckResult(
            name="no_customer_validation_precision_recall",
            ok=not any(d.entity_id == "precision_recall" for d in defects),
            detail="validation Precision/Recall not present as customer fields",
        )
    )
    return checks, defects


def _collect_keys(node: object, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            key = str(k)
            keys.add(key.lower())
            keys |= _collect_keys(v, key)
    elif isinstance(node, list):
        for item in node[:20]:
            keys |= _collect_keys(item, prefix)
    return keys
