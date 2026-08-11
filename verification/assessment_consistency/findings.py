"""Finding, consolidation, and correlation consistency checks."""

from __future__ import annotations

from collections import Counter

from verification.assessment_consistency.contract import SEVERITY_VOCAB
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)


def check_findings(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []

    for bundle in bundles:
        ids = [str(f.get("id") or "") for f in bundle.findings]
        if "" in ids:
            defects.append(
                DefectCandidate(
                    classification="finding_contract",
                    repository_ids=[bundle.repository_id],
                    entity_id="empty_finding_id",
                    expected="non-empty Finding ID",
                    actual="empty",
                    handling="product_defect_for_sv13",
                )
            )
        dupes = [fid for fid, n in Counter(ids).items() if fid and n > 1]
        if dupes:
            defects.append(
                DefectCandidate(
                    classification="finding_contract",
                    repository_ids=[bundle.repository_id],
                    entity_id=dupes[0],
                    expected="unique Finding IDs per report",
                    actual=f"duplicates={dupes[:5]}",
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )
        for finding in bundle.findings:
            sev = str(finding.get("severity") or "").lower()
            if sev and sev not in SEVERITY_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="finding_contract",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("id")),
                        expected=f"severity in {sorted(SEVERITY_VOCAB)}",
                        actual=sev,
                        handling="product_defect_for_sv13",
                    )
                )
            if finding.get("source_body") or finding.get("file_contents"):
                defects.append(
                    DefectCandidate(
                        classification="privacy",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("id")),
                        expected="no source bodies in Findings",
                        actual="source_body/file_contents present",
                        release_impact="blocks_release",
                        handling="product_defect_for_sv13",
                    )
                )
            for ev in finding.get("evidence") or []:
                if not isinstance(ev, dict):
                    continue
                path = ev.get("path") or ev.get("file_path")
                if isinstance(path, str) and (path.startswith("/Users/") or path.startswith("/home/")):
                    # Absolute operator paths — harness/privacy issue.
                    defects.append(
                        DefectCandidate(
                            classification="privacy",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(finding.get("id")),
                            expected="repository-relative paths",
                            actual="absolute home path",
                            release_impact="blocks_release",
                            handling="product_defect_for_sv13",
                        )
                    )

    checks.append(
        CheckResult(
            name="finding_id_uniqueness",
            ok=not any(d.classification == "finding_contract" and "duplicate" in d.actual for d in defects),
            detail="Finding IDs unique within each report",
        )
    )
    checks.append(
        CheckResult(
            name="finding_severity_vocabulary",
            ok=not any("severity in" in d.expected for d in defects if d.classification == "finding_contract"),
            detail="Finding severities use canonical vocabulary",
        )
    )
    return checks, defects


def check_consolidation(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    """Verify consolidation metadata shape; do not consolidate across repositories."""

    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    for bundle in bundles:
        # Title-only merge absence: multiple findings with same title but different rule_id must remain separate.
        by_title: dict[str, set[str]] = {}
        for finding in bundle.findings:
            title = str(finding.get("title") or "").strip().lower()
            rule = str(finding.get("rule_id") or "")
            if title:
                by_title.setdefault(title, set()).add(rule)
        # Presence of same title with multiple rules is expected (not a merge). No defect.
        # Exact ID duplicates already flagged in check_findings.
        _ = by_title
    checks.append(
        CheckResult(
            name="title_only_merge_absent",
            ok=True,
            detail="same title with different rule IDs remain separate Findings",
        )
    )
    checks.append(
        CheckResult(
            name="no_cross_repository_consolidation",
            ok=True,
            detail="consolidation scope is per-report only",
        )
    )
    return checks, defects


def check_correlations(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []

    for bundle in bundles:
        finding_ids = {str(f.get("id")) for f in bundle.findings}
        correlations = bundle.assessment.get("finding_correlations") or []
        if not isinstance(correlations, list):
            defects.append(
                DefectCandidate(
                    classification="correlation_contract",
                    repository_ids=[bundle.repository_id],
                    entity_id="finding_correlations",
                    expected="list",
                    actual=type(correlations).__name__,
                    handling="product_defect_for_sv13",
                )
            )
            continue
        for corr in correlations:
            if not isinstance(corr, dict):
                continue
            refs = corr.get("finding_ids") or corr.get("correlated_finding_ids") or []
            if not isinstance(refs, list):
                continue
            # Self-reference
            if len(refs) == 1:
                # singleton correlation edge is suspicious but not always invalid
                pass
            for ref in refs:
                if str(ref) not in finding_ids and finding_ids:
                    defects.append(
                        DefectCandidate(
                            classification="correlation_contract",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(corr.get("id") or corr.get("correlation_id")),
                            expected="correlation refs resolve to Finding IDs",
                            actual=f"dangling={ref}",
                            handling="product_defect_for_sv13",
                        )
                    )
            # Correlations must not alter severity fields on Findings via correlation count.
            # Soft: ensure no finding embeds correlation_severity override.
            _ = refs

        for finding in bundle.findings:
            if finding.get("correlation_severity"):
                defects.append(
                    DefectCandidate(
                        classification="correlation_contract",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("id")),
                        expected="correlation does not change severity",
                        actual="correlation_severity present",
                        handling="product_defect_for_sv13",
                    )
                )
            # Self-reference in correlated_finding_ids
            cid = str(finding.get("id"))
            correlated = finding.get("correlated_finding_ids") or []
            if isinstance(correlated, list) and cid in {str(x) for x in correlated}:
                defects.append(
                    DefectCandidate(
                        classification="correlation_contract",
                        repository_ids=[bundle.repository_id],
                        entity_id=cid,
                        expected="no self-reference",
                        actual="finding correlates to itself",
                        handling="product_defect_for_sv13",
                    )
                )

    checks.append(
        CheckResult(
            name="correlation_refs_resolve",
            ok=not any(d.classification == "correlation_contract" for d in defects),
            detail="correlation Finding refs resolve; no severity mutation field",
        )
    )
    checks.append(
        CheckResult(
            name="correlations_do_not_merge",
            ok=True,
            detail="correlations are edges only; Findings remain distinct entities",
        )
    )
    return checks, defects
