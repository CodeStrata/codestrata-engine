"""Load and select repositories from the permanent catalog."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from verification.repository_assessment.contract import (
    CATALOG_RELATIVE_PATH,
    CATALOG_SCHEMA_NAME,
)


@dataclass(frozen=True, slots=True)
class QualifiedRevision:
    revision_type: str  # commit | tag
    value: str
    source_tag: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    id: str
    project_name: str
    github_repository: str
    github_url: str
    language_group: str
    candidate_category: str
    license: str
    qualified_revision: QualifiedRevision | None
    enabled_for_smoke: bool
    selection_reason: str = ""


@dataclass(frozen=True, slots=True)
class CatalogView:
    catalog_id: str
    schema_name: str
    schema_version: str
    path: str  # repo-relative display path only
    entries: tuple[CatalogEntry, ...]
    qualification_gap: bool


_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_FLOATING = frozenset({"main", "master", "head", "default", "latest", "origin/main", "origin/master"})


def _parse_revision(raw: Any) -> QualifiedRevision | None:
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip():
        value = raw.strip()
        if _FULL_SHA.match(value.lower()) and len(value) == 40:
            return QualifiedRevision("commit", value.lower())
        if value.lower() in _FLOATING:
            return None
        return QualifiedRevision("tag", value)
    if isinstance(raw, dict):
        rtype = str(raw.get("type") or raw.get("revision_type") or "").strip().lower()
        value = str(raw.get("value") or raw.get("revision") or "").strip()
        source_tag = raw.get("source_tag")
        source = str(source_tag).strip() if isinstance(source_tag, str) and source_tag.strip() else None
        if rtype not in {"commit", "tag"} or not value:
            return None
        if value.lower() in _FLOATING:
            return None
        if rtype == "commit":
            if not _FULL_SHA.match(value.lower()) or len(value) != 40:
                return None
            return QualifiedRevision("commit", value.lower(), source)
        return QualifiedRevision("tag", value, source)
    return None


def resolve_catalog_path(repo_root: Path) -> Path:
    """Resolve catalog from monorepo root or adjacent validation/."""

    candidates = [
        repo_root / CATALOG_RELATIVE_PATH,
        repo_root.parent / CATALOG_RELATIVE_PATH,  # engine/ → monorepo
        repo_root / "validation" / "repository-catalog" / "catalog.json",
    ]
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(
        f"permanent catalog not found; expected {CATALOG_RELATIVE_PATH}"
    )


def load_catalog(repo_root: Path) -> CatalogView:
    path = resolve_catalog_path(repo_root)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_name") != CATALOG_SCHEMA_NAME:
        raise ValueError(f"unexpected catalog schema_name: {data.get('schema_name')!r}")
    entries: list[CatalogEntry] = []
    for item in data.get("repositories") or []:
        if not isinstance(item, dict):
            continue
        enabled = item.get("enabled_for") or {}
        entries.append(
            CatalogEntry(
                id=str(item.get("id") or ""),
                project_name=str(item.get("project_name") or ""),
                github_repository=str(item.get("github_repository") or ""),
                github_url=str(item.get("github_url") or ""),
                language_group=str(item.get("language_group") or ""),
                candidate_category=str(item.get("candidate_category") or ""),
                license=str(item.get("license") or ""),
                qualified_revision=_parse_revision(item.get("qualified_revision")),
                enabled_for_smoke=bool(enabled.get("smoke")),
            )
        )
    qualified = [e for e in entries if e.qualified_revision is not None]
    # Display path relative to monorepo when possible.
    display = CATALOG_RELATIVE_PATH
    return CatalogView(
        catalog_id=str(data.get("catalog_id") or ""),
        schema_name=str(data.get("schema_name") or ""),
        schema_version=str(data.get("schema_version") or ""),
        path=display,
        entries=tuple(entries),
        qualification_gap=len(qualified) == 0,
    )


def select_smoke_repository(catalog: CatalogView) -> tuple[CatalogEntry | None, str]:
    """Deterministic selection per SV.4 policy."""

    candidates = [
        e
        for e in catalog.entries
        if e.enabled_for_smoke and e.qualified_revision is not None
    ]
    if not candidates:
        return None, "no smoke-enabled catalog entry has a qualified commit/tag revision"

    def sort_key(entry: CatalogEntry) -> tuple[int, int, str]:
        category_rank = {
            "Small": 0,
            "Medium": 1,
            "Large": 2,
            "Known Issues": 3,
        }.get(entry.candidate_category, 9)
        # Prefer common supported language groups.
        lang_rank = 0 if entry.language_group in {"JS/TS", "Python", "Java", "C#/.NET"} else 1
        return (category_rank, lang_rank, entry.id)

    chosen = sorted(candidates, key=sort_key)[0]
    reason = (
        f"smoke-enabled; qualified {chosen.qualified_revision.revision_type}="
        f"{chosen.qualified_revision.value}; category={chosen.candidate_category}; "
        f"language={chosen.language_group}; tie-break id={chosen.id}"
    )
    return CatalogEntry(
        id=chosen.id,
        project_name=chosen.project_name,
        github_repository=chosen.github_repository,
        github_url=chosen.github_url,
        language_group=chosen.language_group,
        candidate_category=chosen.candidate_category,
        license=chosen.license,
        qualified_revision=chosen.qualified_revision,
        enabled_for_smoke=chosen.enabled_for_smoke,
        selection_reason=reason,
    ), reason


def find_entry(catalog: CatalogView, repository_id: str) -> CatalogEntry | None:
    for entry in catalog.entries:
        if entry.id == repository_id:
            return entry
    return None
