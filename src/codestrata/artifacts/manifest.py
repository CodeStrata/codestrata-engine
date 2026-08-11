"""Lightweight assessment and artifact-index manifests (Slice 17.12)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codestrata import __version__ as ENGINE_VERSION
from codestrata.artifacts.heads import list_completed_heads

ASSESSMENT_JSON_BASENAME = "assessment.json"
ASSESSMENT_HTML_BASENAME = "assessment.html"
ARTIFACT_MANIFEST_BASENAME = "artifact-manifest.json"
ASSESSMENT_MANIFEST_SCHEMA = "codestrata-assessment-manifest:1.0.0"
ARTIFACT_INDEX_SCHEMA = "codestrata-artifact-manifest:1.0.0"

# Data Lake boundary: assessment/intelligence reports must never auto-upload.
DATA_LAKE_UPLOAD_FORBIDDEN = True


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_assessment_manifest(
    *,
    assessment_id: str,
    repository: str,
    run_directory: Path,
    engine_version: str | None = None,
    schema_version: str = ASSESSMENT_MANIFEST_SCHEMA,
    git_metadata: dict[str, Any] | None = None,
    execution_status: str = "completed",
    overall_summary: str | None = None,
    overall_scores: dict[str, Any] | None = None,
    findings_summary: dict[str, Any] | None = None,
    executed_at: str | None = None,
    repository_id: str | None = None,
    artifact_slot: str | None = None,
    previous_assessment_run_id: str | None = None,
) -> dict[str, Any]:
    """Build the authoritative lightweight assessment manifest.

    Does **not** embed assessment head payloads — heads remain source of truth.
    """

    heads = list_completed_heads(run_directory)
    payload: dict[str, Any] = {
        "schema": schema_version,
        "assessment_id": assessment_id,
        "assessment_run_id": assessment_id,
        "repository": repository,
        "repository_name": repository,
        "executed_at": executed_at or _utc_now_iso(),
        "created_at": executed_at or _utc_now_iso(),
        "engine_version": engine_version or ENGINE_VERSION,
        "execution_status": execution_status,
        "git": git_metadata or {},
        "summary": overall_summary,
        "scores": overall_scores or {},
        "findings_summary": findings_summary or {},
        "completed_heads": heads,
        "head_references": [
            {"head_id": item["head_id"], "path": item["path"]} for item in heads
        ],
        "reports": {
            "assessment_json": ASSESSMENT_JSON_BASENAME,
            "assessment_html": ASSESSMENT_HTML_BASENAME,
        },
        "boundaries": {
            "data_lake_upload_forbidden": DATA_LAKE_UPLOAD_FORBIDDEN,
            "telemetry_does_not_include_reports": True,
            "local_artifact_authority": ".codestrata-artifacts",
        },
    }
    if repository_id:
        payload["repository_id"] = repository_id
    if artifact_slot:
        payload["artifact_slot"] = artifact_slot
    if previous_assessment_run_id:
        payload["previous_assessment_run_id"] = previous_assessment_run_id
    return payload


def write_assessment_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    _atomic_write_text(path, text)
    return path


def build_artifact_index_manifest(
    *,
    assessment_runs: list[dict[str, Any]] | None = None,
    intelligence_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Lightweight root index under ``manifests/artifact-manifest.json``."""

    return {
        "schema": ARTIFACT_INDEX_SCHEMA,
        "generated_at": _utc_now_iso(),
        "artifact_root": ".codestrata-artifacts",
        "assessments": sorted(assessment_runs or [], key=lambda item: item.get("run_id", "")),
        "intelligence": sorted(intelligence_runs or [], key=lambda item: item.get("run_id", "")),
        "boundaries": {
            "data_lake_upload_forbidden": DATA_LAKE_UPLOAD_FORBIDDEN,
        },
    }


def write_artifact_index_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    _atomic_write_text(path, text)
    return path


def _atomic_write_text(path: Path, content: str) -> None:
    fd, tmp_name = tempfile_path(path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def tempfile_path(path: Path) -> tuple[int, str]:
    import tempfile

    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    return fd, name
