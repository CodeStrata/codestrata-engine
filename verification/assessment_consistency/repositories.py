"""Catalog reconciliation for SV.11 repository set."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from verification.assessment_consistency.contract import RELEASE_VALIDATION_TARGET
from verification.assessment_consistency.inputs import Sv10InputError
from verification.assessment_consistency.models import CheckResult, DefectCandidate
from verification.curated_repository_validation.catalog import (
    load_catalog_document,
    load_release_validation_entries,
)


def reconcile_with_catalog(
    records: dict[str, dict[str, Any]],
    *,
    engine_root: Path | None = None,
) -> tuple[list[CheckResult], list[DefectCandidate], dict[str, Any]]:
    catalog = load_catalog_document(engine_root)
    entries = load_release_validation_entries(engine_root)
    if len(entries) != RELEASE_VALIDATION_TARGET:
        raise Sv10InputError(
            f"catalog release_validation count {len(entries)} != {RELEASE_VALIDATION_TARGET}"
        )
    by_id = {e.repository_id: e for e in entries}
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []

    missing = sorted(set(by_id) - set(records))
    extra = sorted(set(records) - set(by_id))
    if missing or extra:
        checks.append(
            CheckResult(
                name="catalog_membership",
                ok=False,
                detail=f"missing={missing} extra={extra}",
                classification="artifact_contract",
            )
        )
        defects.append(
            DefectCandidate(
                classification="artifact_contract",
                repository_ids=missing + extra,
                entity_id="catalog_membership",
                expected="exact 22 catalog release_validation IDs",
                actual=f"missing={missing} extra={extra}",
                release_impact="blocks_sv11",
                handling="verification_harness_fix",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="catalog_membership",
                ok=True,
                detail="22/22 catalog IDs present exactly once",
            )
        )

    for rid, entry in sorted(by_id.items()):
        row = records.get(rid)
        if row is None:
            continue
        pin = entry.qualified_revision.value
        q = str(row.get("qualified_revision") or "")
        f = str(row.get("final_checkout_sha") or "")
        if q != pin or f != pin:
            checks.append(
                CheckResult(
                    name="revision_reconcile",
                    ok=False,
                    detail=f"catalog={pin[:12]} record_q={q[:12]} record_f={f[:12]}",
                    repository_ids=[rid],
                    classification="artifact_contract",
                )
            )
            defects.append(
                DefectCandidate(
                    classification="artifact_contract",
                    repository_ids=[rid],
                    entity_id="revision",
                    expected=pin,
                    actual=f"qualified={q} final={f}",
                    release_impact="blocks_sv11",
                    handling="verification_harness_fix",
                )
            )
        required = (
            "assessment_result",
            "report_schema",
            "traceability_validation",
            "source_integrity_verdict",
            "deterministic_mode",
            "ai_executed",
            "telemetry_transmitted",
            "verdict",
        )
        absent = [k for k in required if k not in row]
        if absent:
            checks.append(
                CheckResult(
                    name="record_fields",
                    ok=False,
                    detail=f"missing fields {absent}",
                    repository_ids=[rid],
                    classification="artifact_contract",
                )
            )

    lang = Counter(str(r.get("language_group") or "unknown") for r in records.values())
    eco = Counter(str(r.get("ecosystem") or "unknown") for r in records.values())
    tier = Counter(str(r.get("tier") or "unknown") for r in records.values())
    meta = {
        "catalog_id": catalog.get("catalog_id"),
        "catalog_schema_version": catalog.get("schema_version"),
        "qualified_revisions": {
            e.repository_id: e.qualified_revision.value for e in entries
        },
        "language_distribution": dict(sorted(lang.items())),
        "ecosystem_distribution": dict(sorted(eco.items())),
        "tier_distribution": dict(sorted(tier.items())),
    }
    if not any(c.name == "revision_reconcile" and not c.ok for c in checks):
        checks.append(
            CheckResult(
                name="revision_reconcile",
                ok=True,
                detail="all qualified/final SHAs match catalog pins",
            )
        )
    return checks, defects, meta
