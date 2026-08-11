"""Load release-validation repositories from the permanent catalog only."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from verification.repository_assessment.catalog import QualifiedRevision
from verification.repository_assessment.contract import CATALOG_RELATIVE_PATH


@dataclass(frozen=True, slots=True)
class ReleaseValidationEntry:
    repository_id: str
    project_name: str
    github_repository: str
    github_url: str
    language_group: str | None
    ecosystem: str | None
    tier: str
    license: str | None
    qualified_revision: QualifiedRevision
    requires_submodules: bool
    requires_git_lfs: bool
    roles: dict[str, bool]
    raw: dict[str, Any]


def monorepo_root_from_engine(engine_root: Path) -> Path:
    candidate = engine_root.resolve()
    if (candidate / CATALOG_RELATIVE_PATH).is_file():
        return candidate
    parent = candidate.parent
    if (parent / CATALOG_RELATIVE_PATH).is_file():
        return parent
    raise FileNotFoundError(CATALOG_RELATIVE_PATH)


def _ensure_catalog_imports(monorepo: Path) -> None:
    catalog_dir = str(monorepo / "validation" / "repository-catalog")
    if catalog_dir not in sys.path:
        sys.path.insert(0, catalog_dir)


def load_catalog_document(engine_root: Path) -> dict[str, Any]:
    monorepo = monorepo_root_from_engine(engine_root)
    _ensure_catalog_imports(monorepo)
    from validate_catalog import load_catalog_document as _load

    return _load(monorepo)


def load_release_validation_entries(engine_root: Path) -> tuple[ReleaseValidationEntry, ...]:
    """Return all release_validation-enabled catalog entries (exactly the active set)."""

    monorepo = monorepo_root_from_engine(engine_root)
    _ensure_catalog_imports(monorepo)
    from readiness import enrichment_for, revision_is_qualified_commit
    from validate_catalog import load_catalog_document as _load

    data = _load(monorepo)
    entries: list[ReleaseValidationEntry] = []
    for item in data.get("repositories") or []:
        if not isinstance(item, dict):
            continue
        enriched = enrichment_for(item)
        roles = enriched.get("roles") or {}
        if not roles.get("release_validation"):
            continue
        rev_raw = item.get("qualified_revision")
        if not revision_is_qualified_commit(rev_raw):
            raise ValueError(f"release_validation entry missing commit pin: {item.get('id')}")
        rev = QualifiedRevision(
            revision_type=str(rev_raw["type"]),
            value=str(rev_raw["value"]).lower(),
            source_tag=(
                str(rev_raw["source_tag"]).strip()
                if isinstance(rev_raw.get("source_tag"), str) and rev_raw.get("source_tag")
                else None
            ),
        )
        entries.append(
            ReleaseValidationEntry(
                repository_id=str(item["id"]),
                project_name=str(item.get("project_name") or item["id"]),
                github_repository=str(item["github_repository"]),
                github_url=str(item["github_url"]),
                language_group=item.get("language_group"),
                ecosystem=enriched.get("dependency_ecosystem"),
                tier=str(enriched.get("expected_runtime_tier") or "tier3"),
                license=item.get("license"),
                qualified_revision=rev,
                requires_submodules=bool(item.get("requires_submodules")),
                requires_git_lfs=bool(item.get("requires_git_lfs")),
                roles={k: bool(v) for k, v in roles.items()},
                raw=item,
            )
        )
    entries.sort(key=lambda e: e.repository_id)
    return tuple(entries)


def assert_readiness_pass(engine_root: Path) -> dict[str, Any]:
    monorepo = monorepo_root_from_engine(engine_root)
    _ensure_catalog_imports(monorepo)
    from readiness import build_readiness_report
    from validate_catalog import load_catalog_document as _load

    report = build_readiness_report(_load(monorepo))
    if report.get("verdict") != "PASS":
        raise RuntimeError(
            "SV.10 blocked: catalog readiness verdict is "
            f"{report.get('verdict')!r}; resolve SV.10A/SV.10B first"
        )
    return report


def to_sv4_catalog_entry(entry: ReleaseValidationEntry):
    """Adapt an SV.10 entry to the SV.4 CatalogEntry shape for clone reuse."""

    from verification.repository_assessment.catalog import CatalogEntry

    return CatalogEntry(
        id=entry.repository_id,
        project_name=entry.project_name,
        github_repository=entry.github_repository,
        github_url=entry.github_url,
        language_group=str(entry.language_group or ""),
        candidate_category=str(entry.raw.get("candidate_category") or ""),
        license=str(entry.license or ""),
        qualified_revision=entry.qualified_revision,
        enabled_for_smoke=bool(entry.roles.get("smoke")),
        selection_reason="sv10_release_validation",
    )
