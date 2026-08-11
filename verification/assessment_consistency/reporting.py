"""Reporting helpers and Engineering Intelligence input readiness."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from codestrata.security.customer_safe_text import ensure_customer_safe_report_document
from verification.assessment_consistency.contract import ASSESSMENT_SCHEMA_VERSION
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)
from verification.assessment_consistency.platform_ingestion_adapter import (
    validate_with_platform_ingestion_safety,
)


def stable_report_digest(report: dict[str, Any]) -> str:
    """Digest excluding volatile timestamps."""

    payload = json.loads(json.dumps(report))
    assessment = payload.get("assessment")
    if isinstance(assessment, dict):
        assessment.pop("generated_at", None)
        assessment.pop("timing", None)
        ai = assessment.get("ai")
        if isinstance(ai, dict):
            ai.pop("latency_ms", None)
    manifest = payload.get("manifest")
    if isinstance(manifest, dict):
        manifest.pop("generated_at", None)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def check_engineering_intelligence_input_ready(
    bundles: list[RepositoryBundle],
) -> tuple[dict[str, bool], list[CheckResult], list[DefectCandidate]]:
    """EI readiness: schema + identity + Platform ingestion safety authority.

    Applies the Engine customer-safe report projection, then invokes the same
    ``validate_report_document`` gate used by production EI ingestion. Does not
    duplicate Platform secret detectors.
    """

    ready: dict[str, bool] = {}
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []

    for bundle in bundles:
        reasons: list[str] = []
        if str(bundle.report.get("schema_version")) != ASSESSMENT_SCHEMA_VERSION:
            reasons.append("schema")
        assessment = bundle.assessment
        if not (bundle.record.get("repository_id") and bundle.record.get("final_checkout_sha")):
            reasons.append("identity")
        if not isinstance(assessment.get("assessment_coverage"), dict):
            reasons.append("coverage_map")
        if not isinstance(assessment.get("assessment_head_confidence"), dict):
            reasons.append("confidence_map")
        if assessment.get("findings") is None and not bundle.findings:
            reasons.append("findings")
        blob = json.dumps({"findings": bundle.findings[:5]}, sort_keys=True)
        if '"source_body"' in blob or '"file_contents"' in blob:
            reasons.append("unsafe_source")

        safe_doc = ensure_customer_safe_report_document(bundle.report)
        ok_platform, platform_reason = validate_with_platform_ingestion_safety(safe_doc)
        if not ok_platform:
            reasons.append(platform_reason or "platform_validation_error")

        _ = stable_report_digest(safe_doc)
        ok = not reasons
        ready[bundle.repository_id] = ok
        if not ok:
            defects.append(
                DefectCandidate(
                    classification="engineering_intelligence_input",
                    repository_ids=[bundle.repository_id],
                    entity_id="ei_input",
                    expected=(
                        "schema 1.2 + identity + head maps + Platform "
                        "validate_report_document acceptance"
                    ),
                    actual=",".join(reasons),
                    release_impact="blocks_sv12_input",
                    handling="product_defect_for_sv13",
                )
            )

    checks.append(
        CheckResult(
            name="engineering_intelligence_input_ready",
            ok=all(ready.values()) and len(ready) == len(bundles),
            detail=(
                f"{sum(1 for v in ready.values() if v)}/{len(bundles)} ready "
                "(Platform ingestion safety)"
            ),
        )
    )
    return ready, checks, defects
