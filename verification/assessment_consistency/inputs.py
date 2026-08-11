"""Load and validate SV.10 inputs for SV.11 (fail closed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verification.assessment_consistency.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    RELEASE_VALIDATION_TARGET,
    SV10_OUTPUT_RELATIVE,
)
from verification.assessment_consistency.models import RepositoryBundle
from verification.cli_installation.environment import engine_root_from_package
from verification.curated_repository_validation.contract import SCHEMA_NAME as SV10_SCHEMA
from verification.repository_assessment.contract import REQUIRED_ARTIFACT_NAMES


class Sv10InputError(RuntimeError):
    """Raised when SV.10 inputs are incomplete or unsafe."""


def default_sv10_dir(engine_root: Path | None = None) -> Path:
    engine = (engine_root or engine_root_from_package()).resolve()
    return engine / SV10_OUTPUT_RELATIVE


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Sv10InputError(f"expected object JSON: {path.name}")
    return payload


def load_sv10_final_report(sv10_dir: Path) -> dict[str, Any]:
    path = sv10_dir / "curated-repository-validation.json"
    if not path.is_file():
        raise Sv10InputError("missing curated-repository-validation.json")
    report = _read_json(path)
    if report.get("schema_name") != SV10_SCHEMA:
        raise Sv10InputError(
            f"unexpected SV.10 schema_name={report.get('schema_name')!r}"
        )
    return report


def load_sv10_records(sv10_dir: Path) -> dict[str, dict[str, Any]]:
    root = sv10_dir / "records"
    if not root.is_dir():
        raise Sv10InputError("missing SV.10 records/ directory")
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        row = _read_json(path)
        rid = str(row.get("repository_id") or path.stem)
        if rid in records:
            raise Sv10InputError(f"duplicate repository record: {rid}")
        if path.stem != rid:
            raise Sv10InputError(
                f"record filename {path.name} does not match repository_id={rid}"
            )
        records[rid] = row
    if len(records) != RELEASE_VALIDATION_TARGET:
        raise Sv10InputError(
            f"expected {RELEASE_VALIDATION_TARGET} records, found {len(records)}"
        )
    return records


def _resolve_artifact_dir(sv10_dir: Path, repository_id: str, sha: str) -> Path:
    base = sv10_dir / "artifacts" / repository_id
    if not base.is_dir():
        raise Sv10InputError(f"missing artifacts for {repository_id}")
    preferred = base / sha[:12]
    if preferred.is_dir():
        return preferred
    children = sorted(p for p in base.iterdir() if p.is_dir())
    if len(children) == 1:
        return children[0]
    if not children:
        raise Sv10InputError(f"empty artifact directory for {repository_id}")
    raise Sv10InputError(
        f"ambiguous artifact directories for {repository_id}: "
        f"expected sha12={sha[:12]}"
    )


def _html_has_csp(html_path: Path) -> bool:
    text = html_path.read_text(encoding="utf-8", errors="replace")[:200_000]
    return "Content-Security-Policy" in text or "content-security-policy" in text


def load_repository_bundle(
    sv10_dir: Path,
    repository_id: str,
    record: dict[str, Any],
) -> RepositoryBundle:
    sha = str(record.get("final_checkout_sha") or record.get("qualified_revision") or "")
    if len(sha) < 12:
        raise Sv10InputError(f"{repository_id}: missing checkout SHA")
    run_dir = _resolve_artifact_dir(sv10_dir, repository_id, sha)
    for name in REQUIRED_ARTIFACT_NAMES:
        if not (run_dir / name).is_file():
            raise Sv10InputError(
                f"{repository_id}: missing required artifact {name}"
            )
    report = _read_json(run_dir / "report.json")
    schema = str(report.get("schema_version") or "")
    if schema != ASSESSMENT_SCHEMA_VERSION:
        raise Sv10InputError(
            f"{repository_id}: unsupported schema_version={schema!r}"
        )
    findings_doc = _read_json(run_dir / "findings.json")
    recommendations_doc = _read_json(run_dir / "recommendations.json")
    html_path = run_dir / "report.html"
    return RepositoryBundle(
        repository_id=repository_id,
        record=record,
        report=report,
        findings_doc=findings_doc,
        recommendations_doc=recommendations_doc,
        artifact_dir_name=run_dir.name,
        html_present=True,
        html_has_csp=_html_has_csp(html_path),
    )


def load_all_bundles(
    sv10_dir: Path | None = None,
    *,
    engine_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[RepositoryBundle]]:
    root = (sv10_dir or default_sv10_dir(engine_root)).resolve()
    if not root.is_dir():
        raise Sv10InputError(f"SV.10 output directory missing: {root.name}")
    final_report = load_sv10_final_report(root)
    records = load_sv10_records(root)
    bundles = [
        load_repository_bundle(root, rid, records[rid])
        for rid in sorted(records)
    ]
    return final_report, records, bundles
