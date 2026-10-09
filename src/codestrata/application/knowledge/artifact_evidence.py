"""Bounded local evidence query service over filesystem artifacts.

This service serves read-only queries directly from local artifact files
(e.g., canonical report.json, assessment.json, FileKnowledgeStore layouts,
and .codestrata-artifacts trees) without opening or querying any database,
executing assessments, activating rules, or making remote calls.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from codestrata.application.knowledge.queries.errors import (
    ArtifactNotFoundError,
    ArtifactPathSecurityError,
    AssessmentRunNotFoundError,
    ComponentNotFoundError,
    DependencyNotFoundError,
    EvidenceNotFoundError,
    FindingNotFoundError,
    MetricNotFoundError,
    QueryBudgetExceededError,
    QueryLimitError,
    RepositoryQueryNotFoundError,
    SnapshotNotFoundError,
    UnknownArtifactVersionError,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_LIMIT = 50
MAX_QUERY_BUDGET_LIMIT = 500
MAX_CHARACTER_BUDGET = 50_000

SUPPORTED_SCHEMA_VERSIONS = frozenset(
    {
        "1",
        "1.0",
        "1.1",
        "1.2",
        "1.0.0",
        "1.2.0",
        "codestrata-assessment-manifest:1.0.0",
        "codestrata-artifact-manifest:1.0.0",
        "codestrata-file-knowledge-store",
    }
)

ALLOWED_ARTIFACT_EXTENSIONS = frozenset({".json", ".jsonl", ".txt", ".sarif"})


class LocalArtifactEvidenceService:
    """Read-only evidence query service over local filesystem artifacts.

    Strictly bounded:
    - Zero database connection (no SQLite/Postgres).
    - Strict local root scoping and path traversal rejection.
    - Version validation for artifact manifests.
    - Bounded pagination and query budget enforcement.
    - No mutations, assessments, rule activations, shell, or remote calls.
    """

    def __init__(self, allowed_root: Path | str | None = None) -> None:
        self._allowed_root: Path | None = (
            Path(allowed_root).resolve() if allowed_root is not None else None
        )

    @staticmethod
    def _as_dict(value: object) -> dict[str, Any]:
        """Safely ensure value is treated as a dict for type safety."""
        if isinstance(value, dict):
            return value
        return {}

    # ------------------------------------------------------------------
    # Security and Validation
    # ------------------------------------------------------------------

    def validate_scope(self, local_root: str | Path) -> Path:
        """Validate that local_root exists, is a directory, and within allowed boundaries."""
        raw_str = str(local_root).strip()
        if not raw_str:
            raise ArtifactPathSecurityError("local_root must be a non-empty string")
        if "\0" in raw_str:
            raise ArtifactPathSecurityError("local_root contains illegal characters")
        if ".." in raw_str:
            raise ArtifactPathSecurityError(f"Path traversal forbidden: {raw_str}")

        resolved = Path(raw_str).resolve()
        if self._allowed_root is None:
            raise ArtifactPathSecurityError("artifact queries require an authorized root")
        if resolved != self._allowed_root and self._allowed_root not in resolved.parents:
            raise ArtifactPathSecurityError(
                f"local_root {raw_str!r} escapes the authorized root {self._allowed_root}"
            )

        if not resolved.exists():
            raise ArtifactPathSecurityError(f"local_root does not exist: {raw_str}")
        if not resolved.is_dir():
            raise ArtifactPathSecurityError(f"local_root is not a directory: {raw_str}")

        resolved_str = str(resolved).lower()
        if resolved_str in {"/", "c:\\", "c:/", "\\"} or resolved_str.startswith(
            ("c:\\windows", "/etc", "/sys", "/proc", "/dev", "/root")
        ):
            raise ArtifactPathSecurityError("Access to system directory is forbidden")

        return resolved

    def validate_subpath(self, subpath: str | Path, root: Path) -> Path:
        """Validate that subpath stays inside root and only targets safe artifact files."""
        sub_str = str(subpath).strip()
        if not sub_str:
            return root
        if ".." in sub_str:
            raise ArtifactPathSecurityError(f"Path traversal forbidden: {sub_str}")

        target = (root / sub_str).resolve()
        if target != root and root not in target.parents:
            raise ArtifactPathSecurityError(f"Path escapes root scope: {sub_str}")

        if target.is_file():
            if target.suffix.lower() not in ALLOWED_ARTIFACT_EXTENSIONS:
                raise ArtifactPathSecurityError(
                    f"Unauthorized file type {target.suffix!r}: only artifact files allowed"
                )

        return target

    def validate_artifact_version(
        self,
        document: Mapping[str, Any],
        source_path: Path | None = None,
    ) -> str:
        """Verify that document schema/version is recognized and supported."""
        raw_version: object = (
            document.get("schema_version")
            or document.get("schema")
            or document.get("version")
            or document.get("format")
        )
        if isinstance(raw_version, Mapping):
            raw_version = raw_version.get("schema_version") or raw_version.get("version")

        if raw_version is None:
            manifest = document.get("manifest")
            if isinstance(manifest, Mapping):
                raw_version = manifest.get("schema_version") or manifest.get("version")

        if raw_version is None:
            raise UnknownArtifactVersionError(
                f"Missing schema version in artifact: {source_path or 'document'}"
            )

        version_str = str(raw_version).strip()
        if version_str not in SUPPORTED_SCHEMA_VERSIONS:
            raise UnknownArtifactVersionError(
                f"Unknown artifact version {version_str!r} in {source_path or 'document'}"
            )
        return version_str

    def validate_pagination(
        self,
        *,
        limit: int,
        offset: int,
        max_limit: int = MAX_QUERY_BUDGET_LIMIT,
    ) -> tuple[int, int]:
        """Validate pagination parameters against budget constraints."""
        if limit < 1:
            raise QueryLimitError("limit must be >= 1")
        if limit > max_limit:
            raise QueryBudgetExceededError(
                f"Requested limit {limit} exceeds maximum query budget of {max_limit}"
            )
        if offset < 0:
            raise QueryLimitError("offset must be >= 0")
        return limit, offset

    # ------------------------------------------------------------------
    # Document Loading Helpers
    # ------------------------------------------------------------------

    def _read_json_file(self, path: Path) -> dict[str, Any]:
        """Safely read a JSON file and validate version."""
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as err:
            raise ArtifactNotFoundError(f"Failed to read artifact {path}: {err}") from err

        if not isinstance(data, dict):
            raise UnknownArtifactVersionError(f"Artifact {path} root must be a JSON object")

        self.validate_artifact_version(data, source_path=path)
        return data

    def _find_candidate_report_files(self, root: Path) -> list[Path]:
        """Discover report and assessment files under the local root."""
        candidates: list[Path] = []
        direct_files = (
            "report.json",
            "assessment.json",
            "store.json",
            "manifest.json",
            "artifact-manifest.json",
        )
        for name in direct_files:
            p = root / name
            if p.is_file():
                candidates.append(p)

        search_dirs = ("assessments", "runs", "reports", "repositories")
        for sdir in search_dirs:
            dp = root / sdir
            if dp.is_dir():
                for sub in dp.iterdir():
                    if sub.is_file() and sub.name in direct_files:
                        candidates.append(sub)
                    elif sub.is_dir():
                        for sub_name in direct_files:
                            nested = sub / sub_name
                            if nested.is_file():
                                candidates.append(nested)
        return candidates

    def _load_canonical_report(
        self,
        local_root: Path,
        run_id: str | None = None,
    ) -> tuple[dict[str, Any], Path]:
        """Locate and load the canonical report or assessment JSON."""
        candidates = self._find_candidate_report_files(local_root)
        if not candidates:
            for stand in ("findings.json", "metrics.json", "components.json"):
                sp = local_root / stand
                if sp.is_file():
                    data = self._read_json_file(sp)
                    return data, sp
            raise ArtifactNotFoundError(f"No CodeStrata artifacts found in {local_root}")

        if run_id:
            compact_run = run_id.strip()
            for cand in candidates:
                if cand.parent.name == compact_run or compact_run in cand.name:
                    data = self._read_json_file(cand)
                    return data, cand
            for cand in candidates:
                data = self._read_json_file(cand)
                doc_run_id = (
                    data.get("assessment_id")
                    or data.get("run_id")
                    or (self._as_dict(data.get("assessment")).get("run_id"))
                )
                if doc_run_id == compact_run:
                    return data, cand
            raise AssessmentRunNotFoundError(f"Assessment run not found: {run_id}")

        for cand in candidates:
            if cand.name in ("report.json", "assessment.json"):
                data = self._read_json_file(cand)
                return data, cand

        first = candidates[0]
        data = self._read_json_file(first)
        return data, first

    # ------------------------------------------------------------------
    # 1. Repositories
    # ------------------------------------------------------------------

    def list_repositories(
        self,
        local_root: str | Path = ".",
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        repositories: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        repos_dir = root / "repositories"
        if repos_dir.is_dir():
            for child in sorted(repos_dir.iterdir()):
                if child.is_dir():
                    manifest_file = child / "repository.json"
                    if manifest_file.is_file():
                        try:
                            data = self._read_json_file(manifest_file)
                            rid = data.get("repository_id") or child.name
                            if rid not in seen_ids:
                                seen_ids.add(rid)
                                repositories.append(
                                    {
                                        "repository_id": rid,
                                        "name": (
                                            data.get("display_name") or data.get("name") or rid
                                        ),
                                        "source_type": data.get("source_type", "local"),
                                        "source_location": data.get("source_location"),
                                        "created_at": data.get("created_at"),
                                    }
                                )
                        except Exception:
                            logger.debug("Failed reading repository manifest %s", manifest_file)

        report_candidates = self._find_candidate_report_files(root)
        for cand in report_candidates:
            try:
                data = self._read_json_file(cand)
                repo_info = data.get("repository") or {}
                if isinstance(repo_info, Mapping):
                    raw_rid = (
                        repo_info.get("id")
                        or repo_info.get("repository_id")
                        or data.get("repository_id")
                        or repo_info.get("name")
                        or "repo-local"
                    )
                    rid = str(raw_rid)
                else:
                    rid = str(repo_info) if repo_info else "repo-local"

                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    name = (
                        repo_info.get("name")
                        if isinstance(repo_info, Mapping)
                        else data.get("repository_name") or rid
                    )
                    repositories.append(
                        {
                            "repository_id": rid,
                            "name": name or rid,
                            "source_type": (
                                repo_info.get("source_type", "local")
                                if isinstance(repo_info, Mapping)
                                else "local"
                            ),
                            "source_location": (
                                repo_info.get("source_location")
                                if isinstance(repo_info, Mapping)
                                else None
                            ),
                            "created_at": data.get("executed_at") or data.get("created_at"),
                        }
                    )
            except Exception:
                continue

        total_count = len(repositories)
        paged = repositories[offset : offset + limit]
        return paged, total_count

    def get_repository(
        self,
        local_root: str | Path = ".",
        repository_id: str = "",
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        rid = repository_id.strip()
        if not rid:
            raise RepositoryQueryNotFoundError("repository_id must not be empty")

        items, _ = self.list_repositories(root, limit=MAX_QUERY_BUDGET_LIMIT, offset=0)
        for item in items:
            if item["repository_id"] == rid or item["name"] == rid:
                return item

        raise RepositoryQueryNotFoundError(f"Repository not found in artifacts: {rid}")

    # ------------------------------------------------------------------
    # 2. Snapshots
    # ------------------------------------------------------------------

    def list_snapshots(
        self,
        local_root: str | Path = ".",
        *,
        repository_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        snapshots: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        repos_dir = root / "repositories"
        if repos_dir.is_dir():
            for repo_dir in repos_dir.iterdir():
                if not repo_dir.is_dir():
                    continue
                if repository_id and repo_dir.name != repository_id:
                    continue
                snaps_dir = repo_dir / "snapshots"
                if snaps_dir.is_dir():
                    for snap_file in sorted(snaps_dir.glob("*.json")):
                        try:
                            data = self._read_json_file(snap_file)
                            sid = data.get("snapshot_id") or snap_file.stem
                            if sid not in seen_ids:
                                seen_ids.add(sid)
                                snapshots.append(
                                    {
                                        "snapshot_id": sid,
                                        "repository_id": repo_dir.name,
                                        "branch": data.get("branch"),
                                        "revision_id": data.get("revision_id"),
                                        "content_fingerprint": data.get("content_fingerprint"),
                                        "created_at": data.get("created_at"),
                                        "file_count": len(
                                            self._as_dict(data.get("manifest")).get("files", [])
                                        ),
                                    }
                                )
                        except Exception:
                            continue

        report_candidates = self._find_candidate_report_files(root)
        for cand in report_candidates:
            try:
                data = self._read_json_file(cand)
                snap_dict = self._as_dict(data.get("snapshot"))
                sid = (
                    data.get("snapshot_id")
                    or data.get("knowledge_snapshot_id")
                    or snap_dict.get("snapshot_id")
                    or snap_dict.get("id")
                )
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    git_dict = self._as_dict(data.get("git"))
                    snapshots.append(
                        {
                            "snapshot_id": sid,
                            "repository_id": data.get("repository_id") or "repo-local",
                            "branch": git_dict.get("branch"),
                            "revision_id": git_dict.get("commit_sha"),
                            "content_fingerprint": data.get("content_fingerprint"),
                            "created_at": data.get("executed_at") or data.get("created_at"),
                            "file_count": data.get("file_count", 0),
                        }
                    )
            except Exception:
                continue

        total_count = len(snapshots)
        paged = snapshots[offset : offset + limit]
        return paged, total_count

    def get_snapshot(
        self,
        local_root: str | Path = ".",
        snapshot_id: str = "",
        repository_id: str | None = None,
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        sid = snapshot_id.strip()
        if not sid:
            raise SnapshotNotFoundError("snapshot_id must not be empty")

        items, _ = self.list_snapshots(
            root,
            repository_id=repository_id,
            limit=MAX_QUERY_BUDGET_LIMIT,
            offset=0,
        )
        for item in items:
            if item["snapshot_id"] == sid:
                return item

        raise SnapshotNotFoundError(f"Snapshot not found in artifacts: {sid}")

    # ------------------------------------------------------------------
    # 3. Components
    # ------------------------------------------------------------------

    def list_components(
        self,
        local_root: str | Path = ".",
        *,
        run_id: str | None = None,
        component_type: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        doc, _ = self._load_canonical_report(root, run_id=run_id)
        assessment = self._as_dict(doc.get("assessment")) or doc
        arch_dict = self._as_dict(assessment.get("architecture"))

        raw_components = (
            assessment.get("components")
            or doc.get("components")
            or arch_dict.get("components")
            or []
        )
        if not isinstance(raw_components, list):
            raw_components = []

        components: list[dict[str, Any]] = []
        comp_filter = component_type.strip().lower() if component_type else None

        for item in raw_components:
            if not isinstance(item, dict):
                continue
            cid = item.get("component_id") or item.get("id") or item.get("name")
            ctype = str(
                item.get("component_type") or item.get("type") or item.get("kind") or "module"
            ).lower()
            if comp_filter and ctype != comp_filter:
                continue
            components.append(
                {
                    "component_id": cid,
                    "name": item.get("name") or cid,
                    "component_type": ctype,
                    "path": item.get("path"),
                    "metrics": item.get("metrics", {}),
                    "dependencies_count": len(item.get("dependencies", [])),
                }
            )

        total_count = len(components)
        paged = components[offset : offset + limit]
        return paged, total_count

    def get_component(
        self,
        local_root: str | Path = ".",
        component_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        cid = component_id.strip()
        if not cid:
            raise ComponentNotFoundError("component_id must not be empty")

        items, _ = self.list_components(root, run_id=run_id, limit=MAX_QUERY_BUDGET_LIMIT, offset=0)
        for item in items:
            if item["component_id"] == cid or item["name"] == cid:
                return item

        raise ComponentNotFoundError(f"Component not found: {cid}")

    # ------------------------------------------------------------------
    # 4. Findings
    # ------------------------------------------------------------------

    def list_findings(
        self,
        local_root: str | Path = ".",
        *,
        run_id: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        doc, _ = self._load_canonical_report(root, run_id=run_id)
        assessment = self._as_dict(doc.get("assessment")) or doc

        raw_findings = assessment.get("findings") or doc.get("findings") or []
        if not isinstance(raw_findings, list):
            raw_findings = []

        sev_filter = severity.strip().lower() if severity else None
        cat_filter = category.strip().lower() if category else None

        findings: list[dict[str, Any]] = []
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            fid = item.get("finding_id") or item.get("id")
            fsev = str(item.get("severity", "medium")).lower()
            fcat = str(item.get("category", "code_quality")).lower()

            if sev_filter and fsev != sev_filter:
                continue
            if cat_filter and fcat != cat_filter:
                continue

            loc = self._as_dict(item.get("location"))
            item_path = item.get("path") or loc.get("path")
            item_line = item.get("line") or loc.get("line")

            findings.append(
                {
                    "finding_id": fid,
                    "rule_id": item.get("rule_id") or item.get("rule"),
                    "severity": fsev,
                    "category": fcat,
                    "message": item.get("message") or item.get("description"),
                    "path": item_path,
                    "line": item_line,
                    "evidence_refs": item.get("evidence_refs", []),
                }
            )

        total_count = len(findings)
        paged = findings[offset : offset + limit]
        return paged, total_count

    def get_finding(
        self,
        local_root: str | Path = ".",
        finding_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        fid = finding_id.strip()
        if not fid:
            raise FindingNotFoundError("finding_id must not be empty")

        items, _ = self.list_findings(root, run_id=run_id, limit=MAX_QUERY_BUDGET_LIMIT, offset=0)
        for item in items:
            if item["finding_id"] == fid:
                return item

        raise FindingNotFoundError(f"Finding not found: {fid}")

    # ------------------------------------------------------------------
    # 5. Metrics
    # ------------------------------------------------------------------

    def list_metrics(
        self,
        local_root: str | Path = ".",
        *,
        run_id: str | None = None,
        category: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        doc, _ = self._load_canonical_report(root, run_id=run_id)
        assessment = self._as_dict(doc.get("assessment")) or doc

        cat_filter = category.strip().lower() if category else None
        metrics: list[dict[str, Any]] = []

        raw_metrics = assessment.get("metrics") or doc.get("metrics") or []
        if not raw_metrics and (root / "metrics.json").is_file():
            try:
                metrics_doc = self._read_json_file(root / "metrics.json")
                raw_metrics = metrics_doc.get("metrics") or metrics_doc
            except Exception:
                pass
        if isinstance(raw_metrics, list):
            for item in raw_metrics:
                if isinstance(item, dict):
                    if _metric_is_ai_claim(item):
                        continue
                    mid = item.get("metric_id") or item.get("name") or item.get("id")
                    mcat = str(item.get("category", "general")).lower()
                    if cat_filter and mcat != cat_filter:
                        continue
                    metrics.append(
                        {
                            "metric_id": mid,
                            "name": item.get("name") or mid,
                            "category": mcat,
                            "value": item.get("value"),
                            "unit": item.get("unit", "count"),
                            "scope": item.get("scope", "repository"),
                            "coverage": item.get("coverage", 1.0),
                            "description": item.get("description"),
                        }
                    )
        elif isinstance(raw_metrics, dict):
            for key, val in raw_metrics.items():
                if cat_filter and "general" != cat_filter:
                    continue
                metrics.append(
                    {
                        "metric_id": key,
                        "name": key,
                        "category": "general",
                        "value": val if not isinstance(val, dict) else val.get("value"),
                        "unit": val.get("unit", "count") if isinstance(val, dict) else "count",
                        "scope": "repository",
                        "coverage": 1.0,
                        "description": None,
                    }
                )

        if not metrics:
            summary = self._as_dict(assessment.get("summary")) or self._as_dict(doc.get("summary"))
            scores = self._as_dict(summary.get("scores")) or self._as_dict(
                summary.get("overall_scores")
            )
            blocked = _unsupported_ai_score_keys(doc, assessment)
            for k, v in scores.items():
                if str(k) in blocked or str(k) in {"health_score", "score"}:
                    continue
                metrics.append(
                    {
                        "metric_id": f"score.{k}",
                        "name": k,
                        "category": "score",
                        "value": v,
                        "unit": "score",
                        "scope": "repository",
                        "coverage": 1.0,
                        "description": f"Overall {k} score",
                    }
                )

        total_count = len(metrics)
        paged = metrics[offset : offset + limit]
        return paged, total_count

    def get_metric(
        self,
        local_root: str | Path = ".",
        metric_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        mid = metric_id.strip()
        if not mid:
            raise MetricNotFoundError("metric_id must not be empty")

        items, _ = self.list_metrics(root, run_id=run_id, limit=MAX_QUERY_BUDGET_LIMIT, offset=0)
        for item in items:
            if item["metric_id"] == mid or item["name"] == mid:
                return item

        raise MetricNotFoundError(f"Metric not found: {mid}")

    def canonical_equivalence_view(
        self,
        local_root: str | Path = ".",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Project canonical findings, metrics, coverage, and verdicts.

        AI explanation objects and unsupported score claims are omitted.
        A missing coverage ratio stays null.
        """

        root = self.validate_scope(local_root)
        doc, _ = self._load_canonical_report(root, run_id=run_id)
        return project_canonical_evidence(doc)

    # ------------------------------------------------------------------
    # 6. Dependencies
    # ------------------------------------------------------------------

    def list_dependencies(
        self,
        local_root: str | Path = ".",
        *,
        run_id: str | None = None,
        source_component_id: str | None = None,
        target_component_id: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        doc, _ = self._load_canonical_report(root, run_id=run_id)
        assessment = self._as_dict(doc.get("assessment")) or doc
        arch_dict = self._as_dict(assessment.get("architecture"))

        raw_deps = (
            assessment.get("dependencies")
            or doc.get("dependencies")
            or arch_dict.get("dependencies")
            or []
        )
        if not isinstance(raw_deps, list):
            raw_deps = []

        src_filter = source_component_id.strip() if source_component_id else None
        tgt_filter = target_component_id.strip() if target_component_id else None

        dependencies: list[dict[str, Any]] = []
        for item in raw_deps:
            if not isinstance(item, dict):
                continue
            src = item.get("source") or item.get("source_component_id") or item.get("from")
            tgt = item.get("target") or item.get("target_component_id") or item.get("to")
            if src_filter and src != src_filter:
                continue
            if tgt_filter and tgt != tgt_filter:
                continue
            rel_type = item.get("relationship_type") or item.get("type", "depends_on")
            dependencies.append(
                {
                    "source": src,
                    "target": tgt,
                    "relationship_type": rel_type,
                    "weight": item.get("weight", 1),
                    "evidence": item.get("evidence", []),
                }
            )

        total_count = len(dependencies)
        paged = dependencies[offset : offset + limit]
        return paged, total_count

    def get_dependencies(
        self,
        local_root: str | Path = ".",
        component_id: str = "",
        run_id: str | None = None,
        direction: str = "outgoing",
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        cid = component_id.strip()
        if not cid:
            raise DependencyNotFoundError("component_id must not be empty")

        dir_clean = direction.strip().lower()
        if dir_clean not in {"incoming", "outgoing", "both"}:
            raise QueryLimitError("direction must be one of: incoming, outgoing, both")

        all_deps, _ = self.list_dependencies(
            root, run_id=run_id, limit=MAX_QUERY_BUDGET_LIMIT, offset=0
        )
        matched: list[dict[str, Any]] = []

        for dep in all_deps:
            if dir_clean == "outgoing" and dep["source"] == cid:
                matched.append(dep)
            elif dir_clean == "incoming" and dep["target"] == cid:
                matched.append(dep)
            elif dir_clean == "both" and (dep["source"] == cid or dep["target"] == cid):
                matched.append(dep)

        limit, offset = self.validate_pagination(limit=limit, offset=offset)
        total_count = len(matched)
        return matched[offset : offset + limit], total_count

    # ------------------------------------------------------------------
    # 7. Changes
    # ------------------------------------------------------------------

    def list_changes(
        self,
        local_root: str | Path = ".",
        *,
        run_id: str | None = None,
        change_type: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        doc, _ = self._load_canonical_report(root, run_id=run_id)
        assessment = self._as_dict(doc.get("assessment")) or doc
        delta_dict = self._as_dict(assessment.get("delta"))

        raw_changes = (
            assessment.get("change_facts")
            or assessment.get("changes")
            or doc.get("change_facts")
            or doc.get("changes")
            or delta_dict.get("changes")
            or []
        )
        if not isinstance(raw_changes, list):
            raw_changes = []

        type_filter = change_type.strip().lower() if change_type else None
        changes: list[dict[str, Any]] = []

        for item in raw_changes:
            if not isinstance(item, dict):
                continue
            ctype = str(item.get("change_type") or item.get("type", "modified")).lower()
            if type_filter and ctype != type_filter:
                continue
            changes.append(
                {
                    "path": item.get("path") or item.get("file_path"),
                    "change_type": ctype,
                    "lineage_status": item.get("lineage_status", "unique"),
                    "diff_stat": item.get("diff_stat", {}),
                    "boundary_crossed": item.get("boundary_crossed", False),
                    "blast_radius": item.get("blast_radius", {}),
                }
            )

        total_count = len(changes)
        paged = changes[offset : offset + limit]
        return paged, total_count

    def get_change_summary(
        self,
        local_root: str | Path = ".",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        doc, _ = self._load_canonical_report(root, run_id=run_id)
        assessment = self._as_dict(doc.get("assessment")) or doc

        delta = self._as_dict(assessment.get("delta")) or self._as_dict(doc.get("delta"))
        summary = (
            self._as_dict(delta.get("summary"))
            or self._as_dict(assessment.get("change_summary"))
            or self._as_dict(doc.get("change_summary"))
        )

        changes, total_changes = self.list_changes(
            root, run_id=run_id, limit=MAX_QUERY_BUDGET_LIMIT, offset=0
        )
        added = sum(1 for c in changes if c["change_type"] == "added")
        deleted = sum(1 for c in changes if c["change_type"] == "deleted")
        modified = sum(1 for c in changes if c["change_type"] == "modified")

        return {
            "total_changes": summary.get("total_changes", total_changes),
            "added_count": summary.get("added_count", added),
            "deleted_count": summary.get("deleted_count", deleted),
            "modified_count": summary.get("modified_count", modified),
            "verdict": summary.get("verdict", delta.get("verdict", "no_baseline")),
            "boundaries_crossed_count": summary.get("boundaries_crossed_count", 0),
            "affected_components_count": summary.get("affected_components_count", 0),
        }

    # ------------------------------------------------------------------
    # 8. Evidence
    # ------------------------------------------------------------------

    def list_evidence(
        self,
        local_root: str | Path = ".",
        *,
        run_id: str | None = None,
        evidence_kind: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        doc, _ = self._load_canonical_report(root, run_id=run_id)
        assessment = self._as_dict(doc.get("assessment")) or doc

        raw_evidence = assessment.get("evidence") or doc.get("evidence") or []
        if not isinstance(raw_evidence, list):
            raw_evidence = []

        kind_filter = evidence_kind.strip().lower() if evidence_kind else None
        evidence_list: list[dict[str, Any]] = []

        for item in raw_evidence:
            if not isinstance(item, dict):
                continue
            ekind = str(item.get("kind") or item.get("evidence_kind", "source")).lower()
            if kind_filter and ekind != kind_filter:
                continue

            eid = item.get("evidence_id") or item.get("id")
            loc = self._as_dict(item.get("location"))
            src_path = item.get("source_path") or loc.get("path")
            lines = item.get("line_range") or loc.get("lines")

            evidence_list.append(
                {
                    "evidence_id": eid,
                    "kind": ekind,
                    "source_path": src_path,
                    "snippet": item.get("snippet") or item.get("detail"),
                    "line_range": lines,
                    "fingerprint": item.get("fingerprint"),
                    "confidence": item.get("confidence", 1.0),
                }
            )

        total_count = len(evidence_list)
        paged = evidence_list[offset : offset + limit]
        return paged, total_count

    def get_evidence(
        self,
        local_root: str | Path = ".",
        evidence_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        eid = evidence_id.strip()
        if not eid:
            raise EvidenceNotFoundError("evidence_id must not be empty")

        items, _ = self.list_evidence(root, run_id=run_id, limit=MAX_QUERY_BUDGET_LIMIT, offset=0)
        for item in items:
            if item["evidence_id"] == eid:
                return item

        raise EvidenceNotFoundError(f"Evidence not found: {eid}")

    # ------------------------------------------------------------------
    # 9. Lineage
    # ------------------------------------------------------------------

    def list_lineage(
        self,
        local_root: str | Path = ".",
        *,
        repository_id: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        root = self.validate_scope(local_root)
        limit, offset = self.validate_pagination(limit=limit, offset=offset)

        candidates = self._find_candidate_report_files(root)
        lineage_records: list[dict[str, Any]] = []
        seen_runs: set[str] = set()

        for cand in candidates:
            try:
                data = self._read_json_file(cand)
                rid = (
                    data.get("assessment_id")
                    or data.get("assessment_run_id")
                    or data.get("run_id")
                    or (cand.parent.name if cand.parent.name != "assessments" else cand.stem)
                )
                if not rid or rid in seen_runs:
                    continue

                repo_dict = self._as_dict(data.get("repository"))
                repo_id = data.get("repository_id") or repo_dict.get("id") or data.get("repository")
                if repository_id and repo_id != repository_id:
                    continue

                seen_runs.add(rid)
                git_info = self._as_dict(data.get("git"))
                prev_run = data.get("previous_assessment_run_id") or data.get("previous_run_id")
                engine_ver = data.get("engine_version") or data.get("codestrata_version")

                lineage_records.append(
                    {
                        "run_id": rid,
                        "repository_id": repo_id or "repo-local",
                        "snapshot_id": (
                            data.get("snapshot_id") or data.get("knowledge_snapshot_id")
                        ),
                        "previous_run_id": prev_run,
                        "git_commit": git_info.get("commit_sha") or git_info.get("commit"),
                        "branch": git_info.get("branch"),
                        "engine_version": engine_ver,
                        "ruleset_version": data.get("ruleset_version"),
                        "invalidation_fingerprint": data.get("invalidation_fingerprint"),
                        "executed_at": data.get("executed_at") or data.get("created_at"),
                        "status": data.get("execution_status") or data.get("status", "completed"),
                    }
                )
            except Exception:
                continue

        total_count = len(lineage_records)
        paged = lineage_records[offset : offset + limit]
        return paged, total_count

    def get_lineage(
        self,
        local_root: str | Path = ".",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        root = self.validate_scope(local_root)
        doc, path = self._load_canonical_report(root, run_id=run_id)

        rid = (
            doc.get("assessment_id")
            or doc.get("assessment_run_id")
            or doc.get("run_id")
            or (path.parent.name if path.parent.name != "assessments" else path.stem)
        )
        git_info = self._as_dict(doc.get("git"))
        repo_dict = self._as_dict(doc.get("repository"))
        repo_id = (
            doc.get("repository_id") or repo_dict.get("id") or doc.get("repository", "repo-local")
        )

        return {
            "run_id": rid,
            "repository_id": repo_id,
            "snapshot_id": doc.get("snapshot_id") or doc.get("knowledge_snapshot_id"),
            "previous_run_id": (
                doc.get("previous_assessment_run_id") or doc.get("previous_run_id")
            ),
            "git_commit": git_info.get("commit_sha") or git_info.get("commit"),
            "branch": git_info.get("branch"),
            "engine_version": doc.get("engine_version") or doc.get("codestrata_version"),
            "ruleset_version": doc.get("ruleset_version"),
            "invalidation_fingerprint": doc.get("invalidation_fingerprint"),
            "executed_at": doc.get("executed_at") or doc.get("created_at"),
            "status": doc.get("execution_status") or doc.get("status", "completed"),
            "completed_heads": doc.get("completed_heads", []),
            "boundaries": doc.get("boundaries", {}),
        }


_AI_CLAIM_CONTAINERS = ("ai_explanation", "explanation", "ai_claims")
_AI_SCORE_KEYS = frozenset({"health_score", "score", "scores", "overall_scores"})


def _metric_is_ai_claim(item: Mapping[str, Any]) -> bool:
    """True when a metric row is an unsupported AI claim rather than a measurement."""

    if item.get("excluded_from_canonical") is True:
        return True
    if item.get("origin") == "ai":
        return True
    metric_id = str(item.get("metric_id") or item.get("name") or item.get("id") or "")
    return metric_id in {"health_score", "score"} or metric_id.startswith("score.health")


def _unsupported_ai_score_keys(
    document: Mapping[str, Any],
    assessment: Mapping[str, Any],
) -> set[str]:
    """Names an AI payload tried to publish as scores."""

    blocked: set[str] = set()
    containers: list[Mapping[str, Any]] = [document, assessment]
    for source in (document, assessment):
        summary = source.get("summary")
        if isinstance(summary, Mapping):
            containers.append(summary)
    for container in containers:
        for name in _AI_CLAIM_CONTAINERS:
            claim = container.get(name)
            if not isinstance(claim, Mapping):
                continue
            for key in claim:
                if key in _AI_SCORE_KEYS or key in {"severity", "verdict", "coverage"}:
                    blocked.add(str(key))
            for nested_name in ("scores", "overall_scores"):
                nested = claim.get(nested_name)
                if isinstance(nested, Mapping):
                    blocked.update(str(key) for key in nested)
    return blocked


def project_canonical_evidence(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical fields an AI explanation is not allowed to change."""

    assessment_raw = document.get("assessment")
    assessment: Mapping[str, Any] = (
        assessment_raw if isinstance(assessment_raw, Mapping) else document
    )
    findings: list[dict[str, Any]] = []
    raw_findings = assessment.get("findings") or document.get("findings") or []
    if isinstance(raw_findings, list):
        for item in raw_findings:
            if not isinstance(item, Mapping) or item.get("origin") == "ai":
                continue
            findings.append(
                {
                    "finding_id": item.get("finding_id") or item.get("id"),
                    "severity": item.get("severity"),
                }
            )

    metrics: list[dict[str, Any]] = []
    raw_metrics = assessment.get("metrics") or document.get("metrics") or []
    if isinstance(raw_metrics, list):
        for item in raw_metrics:
            if not isinstance(item, Mapping) or _metric_is_ai_claim(item):
                continue
            coverage = item.get("coverage") if "coverage" in item else None
            metrics.append(
                {
                    "metric_id": item.get("metric_id") or item.get("name") or item.get("id"),
                    "value": item.get("value"),
                    "coverage": coverage,
                }
            )

    coverage_rows: list[dict[str, Any]] = []
    raw_coverage = assessment.get("coverage") or document.get("coverage") or []
    if isinstance(raw_coverage, list):
        for item in raw_coverage:
            if not isinstance(item, Mapping) or item.get("origin") == "ai":
                continue
            if "coverage_ratio" in item:
                ratio: Any = item.get("coverage_ratio")
            elif "coverage" in item:
                ratio = item.get("coverage")
            else:
                ratio = None
            coverage_rows.append(
                {
                    "capability_id": item.get("capability_id"),
                    "coverage_ratio": ratio,
                    "reason": item.get("reason"),
                }
            )

    verdicts: list[dict[str, Any]] = []
    raw_verdicts = assessment.get("verdicts") or document.get("verdicts") or []
    if isinstance(raw_verdicts, list):
        for item in raw_verdicts:
            if not isinstance(item, Mapping) or item.get("origin") == "ai":
                continue
            verdicts.append(
                {
                    "family": item.get("family"),
                    "verdict": item.get("verdict"),
                }
            )

    status = document.get("assessment_status") or assessment.get("assessment_status")
    digest = document.get("canonical_digest") or assessment.get("canonical_digest")
    return {
        "assessment_status": status,
        "canonical_digest": digest,
        "findings": findings,
        "metrics": metrics,
        "coverage": coverage_rows,
        "verdicts": verdicts,
        "rejected_ai_claims": sorted(_unsupported_ai_score_keys(document, assessment)),
    }
