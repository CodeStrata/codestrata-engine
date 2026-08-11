"""Negative scenario helpers for SV.11 tests (fixtures only; never mutate SV.10)."""

from __future__ import annotations

import copy
from typing import Any

from verification.assessment_consistency.models import RepositoryBundle


def clone_bundle(bundle: RepositoryBundle) -> RepositoryBundle:
    return RepositoryBundle(
        repository_id=bundle.repository_id,
        record=copy.deepcopy(bundle.record),
        report=copy.deepcopy(bundle.report),
        findings_doc=copy.deepcopy(bundle.findings_doc),
        recommendations_doc=copy.deepcopy(bundle.recommendations_doc),
        artifact_dir_name=bundle.artifact_dir_name,
        html_present=bundle.html_present,
        html_has_csp=bundle.html_has_csp,
    )


def mutate_schema_version(bundle: RepositoryBundle, version: str) -> RepositoryBundle:
    out = clone_bundle(bundle)
    out.report["schema_version"] = version
    return out


def mutate_duplicate_finding_id(bundle: RepositoryBundle) -> RepositoryBundle:
    out = clone_bundle(bundle)
    findings = out.assessment.get("findings")
    if isinstance(findings, list) and len(findings) >= 2:
        findings[1]["id"] = findings[0]["id"]
    return out


def mutate_dangling_recommendation_support(bundle: RepositoryBundle) -> RepositoryBundle:
    out = clone_bundle(bundle)
    recs = out.assessment.get("deterministic_recommendations")
    if not isinstance(recs, list) or not recs:
        # Fall back to companion doc mutation for tests that use recommendations property.
        recs = out.recommendations_doc.setdefault("recommendations", [])
    if isinstance(recs, list) and recs:
        recs[0]["supporting_finding_ids"] = ["missing-finding-id-sv11"]
        recs[0]["recommendation_type"] = "finding_backed"
        recs[0]["primary_finding_id"] = "missing-finding-id-sv11"
    return out


def mutate_priority_band_mismatch(bundle: RepositoryBundle) -> RepositoryBundle:
    out = clone_bundle(bundle)
    recs = out.assessment.get("deterministic_recommendations")
    if not isinstance(recs, list) or not recs:
        recs = out.recommendations_doc.setdefault("recommendations", [])
    if isinstance(recs, list) and recs:
        recs[0]["priority"] = "low"
        recs[0]["priority_score"] = 95
        pa = dict(recs[0].get("priority_assessment") or {})
        pa["priority"] = "low"
        pa["score"] = 95
        recs[0]["priority_assessment"] = pa
    return out


def mutate_correlation_self_ref(bundle: RepositoryBundle) -> RepositoryBundle:
    out = clone_bundle(bundle)
    findings = out.assessment.get("findings")
    if isinstance(findings, list) and findings:
        fid = findings[0].get("id")
        findings[0]["correlated_finding_ids"] = [fid]
    return out


def mutate_wrong_limitation_repo(bundle: RepositoryBundle) -> RepositoryBundle:
    out = clone_bundle(bundle)
    out.record["limitations"] = [
        "catalog declares submodules; assessed without initializing submodules"
    ]
    return out


def mutate_zero_denominator_ratio(bundle: RepositoryBundle) -> RepositoryBundle:
    out = clone_bundle(bundle)
    cov = out.assessment.setdefault("assessment_coverage", {})
    if isinstance(cov, dict) and cov:
        head = next(iter(cov.values()))
        if isinstance(head, dict):
            head["status"] = "complete"
            areas = head.setdefault("areas", [])
            if isinstance(areas, list):
                areas.append(
                    {
                        "area_id": "sv11_zero_denom",
                        "eligible_rule_count": 0,
                        "executed_rule_count": 0,
                        "coverage_ratio": 0,
                        "claim_state": "claimed",
                        "evaluation_state": "evaluated",
                        "support_state": "supported",
                    }
                )
    return out


def minimal_record(**overrides: Any) -> dict[str, Any]:
    base = {
        "repository_id": "fixture",
        "qualified_revision": "a" * 40,
        "final_checkout_sha": "a" * 40,
        "assessment_result": "pass",
        "report_schema": "1.2",
        "traceability_validation": "pass",
        "source_integrity_verdict": "pass",
        "deterministic_mode": True,
        "ai_executed": False,
        "telemetry_transmitted": False,
        "limitations": [],
        "verdict": "PASS",
        "tier": "tier1",
        "language_group": "Python",
        "ecosystem": "PyPI",
    }
    base.update(overrides)
    return base
