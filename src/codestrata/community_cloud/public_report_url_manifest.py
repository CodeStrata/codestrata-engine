"""Local export/snapshot of the private Community validation registry.

Not production routing state. Only written when an explicit manifest path is
configured or discovered under a monorepo validation suite directory.

Authoritative production copy lives in the private AWS Community report
artifact store (``metadata/validation/entries/``). This file is release-run
evidence only and can be regenerated from Insights / API without changing
opaque public report URLs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

SCHEMA = "public-report-urls-manifest:1.1"
ENV_MANIFEST = "CODESTRATA_PUBLIC_REPORT_URLS_MANIFEST"
DEFAULT_RELATIVE = (
    ".codestrata-artifacts/validation/suites/release-v0.2.0/public-report-urls.json"
)

ReportType = Literal["assessment", "engineering_intelligence"]


def resolve_manifest_path(*, start: Path | None = None) -> Path | None:
    env = (os.environ.get(ENV_MANIFEST) or "").strip()
    if env:
        return Path(env).expanduser()
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        path = candidate / DEFAULT_RELATIVE
        if path.is_file() or (candidate / ".codestrata-artifacts").is_dir():
            if path.parent.is_dir() or path.is_file() or (
                candidate / ".codestrata-artifacts"
            ).is_dir():
                # Prefer writing into monorepo artifacts when present.
                if (candidate / ".git").exists() or (
                    candidate / ".codestrata-artifacts"
                ).is_dir():
                    return path
    return None


def _empty() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "purpose": (
            "Local export/snapshot of the private Community validation registry "
            "for deterministic release evidence — not the authoritative production "
            "copy and not production routing state"
        ),
        "authoritative_registry": "private_community_validation_registry",
        "assessments": [],
        "engineering_intelligence": [],
        "note": (
            "Append/update capable for Release Epic; cloud private validation "
            "registry + report lifecycle remain backend authority. Temporary "
            "internal Community validation tooling."
        ),
        "temporary": True,
    }


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _empty()
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return _empty()
    # Normalize legacy flat entries once.
    if "entries" in doc and "assessments" not in doc:
        assessments = []
        for item in doc.get("entries") or []:
            if not isinstance(item, dict):
                continue
            assessments.append(
                {
                    "repository_id": item.get("repository_id"),
                    "report_type": "assessment",
                    "current_public_url": item.get("public_url"),
                    "previous_public_url": None,
                    "current_status": item.get("status") or "published",
                    "previous_status": None,
                    "last_verified_status": item.get("http_status_observed"),
                    "source_slice": item.get("source_slice"),
                    "note": item.get("note"),
                }
            )
        out = _empty()
        out["assessments"] = assessments
        return out
    out = _empty()
    out["assessments"] = list(doc.get("assessments") or [])
    out["engineering_intelligence"] = list(doc.get("engineering_intelligence") or [])
    return out


def _save(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def record_published_url(
    *,
    report_type: ReportType,
    logical_id: str,
    public_url: str,
    source_slice: str | None = None,
    start: Path | None = None,
) -> Path | None:
    """Upsert current/previous rotation. Returns manifest path or None if skipped."""

    path = resolve_manifest_path(start=start)
    if path is None:
        return None
    doc = _load(path)
    bucket = (
        "assessments" if report_type == "assessment" else "engineering_intelligence"
    )
    id_key = "repository_id" if report_type == "assessment" else "portfolio_id"
    entries = list(doc.get(bucket) or [])
    found: dict[str, Any] | None = None
    for item in entries:
        if isinstance(item, dict) and str(item.get(id_key)) == logical_id:
            found = item
            break
    if found is None:
        found = {
            id_key: logical_id,
            "report_type": report_type,
            "current_public_url": None,
            "previous_public_url": None,
            "current_status": None,
            "previous_status": None,
            "last_verified_status": None,
        }
        entries.append(found)
    old_current = found.get("current_public_url")
    old_status = found.get("current_status")
    if old_current and old_current != public_url:
        found["previous_public_url"] = old_current
        found["previous_status"] = old_status or "published"
    found["current_public_url"] = public_url
    found["current_status"] = "published"
    if source_slice:
        found["source_slice"] = source_slice
    doc[bucket] = entries
    _save(path, doc)
    return path


__all__ = [
    "DEFAULT_RELATIVE",
    "ENV_MANIFEST",
    "SCHEMA",
    "record_published_url",
    "resolve_manifest_path",
]
