"""Map AnalysisResult into the LLM evidence contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from codestrata.ai.contracts.budget import (
    AIContextBudgetError,
    select_findings_for_ai_context,
)
from codestrata.ai.contracts.limits import LLMContractLimits
from codestrata.ai.contracts.models import (
    LLM_CONTRACT_SCHEMA_VERSION,
    LLMAnalysisContext,
    LLMContextBudgetMetadata,
    LLMEvidenceLocation,
    LLMFactsSummary,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRecommendationEvidence,
    LLMRepositoryContext,
    LLMSectionTruncation,
    LLMStaticAnalysisSummary,
    LLMTechnologyEvidence,
)
from codestrata.models import AnalysisResult, Finding, Recommendation, Technology
from codestrata.models.evidence import Evidence
from codestrata.security.redaction import Redactor
from codestrata.static_analysis.visibility import CustomerVisibility

_EXCLUDED_METADATA_KEYS = frozenset(
    {
        "token",
        "password",
        "secret",
        "credential",
        "credentials",
        "authorization",
        "askpass",
        "private_key",
        "api_key",
        "access_token",
        "refresh_token",
        "token_env",
        "executable",
        "command",
        "argv",
        "environment",
        "env",
        "temp_report",
        "output_directory",
        "workspace",
        "helper_path",
        "git_askpass",
    }
)

_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?:^|[\s\"'=])(/Users/|/home/|/tmp/|/var/|/private/|[A-Za-z]:\\)"
)

_MAX_TECHNOLOGIES = 40
_MAX_RECOMMENDATIONS = 25
_MAX_FACT_LIST_ITEMS = 12


class LLMAnalysisContextBuilder:
    """Build a deterministic LLMAnalysisContext from an AnalysisResult."""

    def __init__(
        self,
        *,
        limits: LLMContractLimits | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        self._limits = limits or LLMContractLimits()
        self._redactor = redactor or Redactor()

    def build(self, result: AnalysisResult) -> LLMAnalysisContext:
        """Convert an AnalysisResult into an immutable LLM contract."""

        technologies = self._map_technologies(result.technologies)
        selection = select_findings_for_ai_context(
            result.findings,
            max_findings=self._limits.max_findings,
            max_evidence_per_finding=self._limits.max_evidence_per_finding,
        )
        findings = [self._map_finding(finding) for finding in selection.included]
        findings_truncation = LLMSectionTruncation(
            truncated=selection.truncated,
            original_count=selection.candidate_count,
            included_count=selection.included_count,
        )
        static_summary = self._map_static_analysis(result)
        budget = LLMContextBudgetMetadata(
            candidate_finding_count=selection.candidate_count,
            included_finding_count=selection.included_count,
            omitted_informational_count=selection.omitted_informational_count,
            estimated_input_tokens=selection.estimated_input_tokens,
            static_analysis_profile=static_summary.profile,
        )
        repository = self._map_repository(result)
        metrics = LLMMetricsContext(
            file_count=self._file_count(result),
            source_file_count=(
                result.facts.structure.source_file_count
                if result.facts.structure is not None
                else None
            ),
            test_file_count=(
                result.facts.structure.test_file_count
                if result.facts.structure is not None
                else None
            ),
            finding_count=len(result.findings),
            technology_count=len(result.technologies),
            recommendation_count=len(result.recommendations),
        )

        return LLMAnalysisContext(
            schema_version=LLM_CONTRACT_SCHEMA_VERSION,
            repository=repository,
            technologies=technologies,
            metrics=metrics,
            findings=findings,
            findings_truncation=findings_truncation,
            facts_summary=self._map_facts(result),
            static_analysis_summary=static_summary,
            deterministic_recommendations=self._map_recommendations(result.recommendations),
            warnings=[],
            budget=budget,
        )

    def _map_repository(self, result: AnalysisResult) -> LLMRepositoryContext:
        repository = result.repository
        return LLMRepositoryContext(
            name=self._sanitize_text(repository.name) or "unknown",
            source_type=self._source_type(repository.source_url),
            default_branch=self._sanitize_optional_text(repository.default_branch),
            commit_sha=self._safe_commit_sha(repository.metadata),
            file_count=self._file_count(result),
        )

    def _file_count(self, result: AnalysisResult) -> int:
        if result.repository.total_files is not None:
            return result.repository.total_files
        if result.facts.structure is not None and result.facts.structure.file_count is not None:
            return result.facts.structure.file_count
        return len(result.repository.files)

    def _source_type(self, source_url: str | None) -> str:
        if not source_url:
            return "local"
        lowered = source_url.lower()
        if "github.com" in lowered:
            return "github"
        if lowered.startswith(("http://", "https://", "git@", "ssh://")):
            return "remote"
        return "unknown"

    def _safe_commit_sha(self, metadata: dict[str, Any]) -> str | None:
        raw = metadata.get("commit_sha") or metadata.get("commit")
        if not isinstance(raw, str):
            return None
        compact = raw.strip()
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", compact):
            return None
        return compact.lower()

    def _map_technologies(
        self,
        technologies: list[Technology],
    ) -> list[LLMTechnologyEvidence]:
        ordered = sorted(
            technologies,
            key=lambda item: (
                self._enum_value(item.category),
                item.name.lower(),
                (item.version or "").lower(),
            ),
        )[:_MAX_TECHNOLOGIES]
        mapped: list[LLMTechnologyEvidence] = []
        for technology in ordered:
            evidence_items: list[str] = []
            if technology.source:
                sanitized_source = self._sanitize_text(technology.source)
                if sanitized_source:
                    evidence_items.append(sanitized_source)
            mapped.append(
                LLMTechnologyEvidence(
                    name=self._sanitize_text(technology.name) or technology.name,
                    category=self._enum_value(technology.category),
                    version=self._sanitize_optional_text(technology.version),
                    confidence=technology.confidence,
                    evidence=evidence_items,
                )
            )
        return mapped

    def _map_finding(self, finding: Finding) -> LLMFindingEvidence:
        evidence_items, evidence_truncation = self._map_evidence(finding.evidence)
        affected = sorted(
            {
                sanitized
                for item in finding.affected_technologies
                if (sanitized := self._sanitize_text(item))
            },
            key=str.lower,
        )
        group_id = self._sanitize_optional_text(
            str(finding.metadata.get("group_id"))
            if finding.metadata.get("group_id") is not None
            else None
        )
        finding_id = group_id or self._sanitize_optional_text(str(finding.id))
        occurrence = finding.metadata.get("occurrence_count")
        affected_files = finding.metadata.get("affected_file_count")
        return LLMFindingEvidence(
            finding_id=finding_id,
            rule_id=self._sanitize_optional_text(finding.rule_id),
            group_id=group_id,
            title=self._sanitize_text(finding.title) or finding.title,
            category=self._enum_value(finding.category),
            severity=self._enum_value(finding.severity),
            source=self._enum_value(finding.source),
            summary=self._sanitize_text(finding.description) or "",
            customer_visibility=self._sanitize_optional_text(
                str(finding.metadata.get("customer_visibility"))
                if finding.metadata.get("customer_visibility") is not None
                else CustomerVisibility.PRIMARY.value
            ),
            modernization_relevance=self._sanitize_optional_text(
                str(finding.metadata.get("modernization_relevance"))
                if finding.metadata.get("modernization_relevance") is not None
                else None
            ),
            occurrence_count=occurrence if isinstance(occurrence, int) else None,
            affected_file_count=affected_files if isinstance(affected_files, int) else None,
            mapping_rationale=self._sanitize_optional_text(
                str(finding.metadata.get("mapping_rationale"))
                if finding.metadata.get("mapping_rationale") is not None
                else None
            ),
            evidence=evidence_items,
            affected_technologies=affected,
            metadata=self._map_metadata(finding.metadata),
            evidence_truncation=evidence_truncation,
        )

    def _map_evidence(
        self,
        evidence_items: list[Evidence],
    ) -> tuple[list[LLMEvidenceLocation], LLMSectionTruncation]:
        ordered = sorted(
            evidence_items,
            key=lambda item: (
                item.file_path,
                item.line_number or 0,
                item.column_number or 0,
                item.description or "",
            ),
        )
        original_count = len(ordered)
        included = ordered[: self._limits.max_evidence_per_finding]
        mapped = [self._map_evidence_item(item) for item in included]
        truncation = LLMSectionTruncation(
            truncated=original_count > len(included),
            original_count=original_count,
            included_count=len(included),
        )
        return mapped, truncation

    def _map_evidence_item(self, item: Evidence) -> LLMEvidenceLocation:
        path = item.file_path.strip() if item.file_path else "."
        if path in {".", "./"}:
            path = "."
        else:
            path = self._repository_relative_path(path)
        excerpt_source = item.snippet or item.description or item.detected_value
        return LLMEvidenceLocation(
            path=path,
            line=item.line_number,
            column=item.column_number,
            excerpt=self._truncate_excerpt(excerpt_source),
        )

    def _map_facts(self, result: AnalysisResult) -> LLMFactsSummary:
        facts = result.facts
        return LLMFactsSummary(
            architecture=self._compact_model(facts.architecture),
            build=self._compact_model(facts.build),
            dependencies=self._compact_dependencies(facts.dependencies),
            cicd=self._compact_model(facts.cicd),
            security=self._compact_model(facts.security),
            cloud_readiness=self._compact_model(facts.cloud),
        )

    def _map_static_analysis(self, result: AnalysisResult) -> LLMStaticAnalysisSummary:
        if not result.static_analysis_results:
            return LLMStaticAnalysisSummary(status="disabled")
        primary = result.static_analysis_results[0]
        rulesets = primary.command_metadata.get("rulesets")
        return LLMStaticAnalysisSummary(
            profile=primary.profile
            or (
                str(primary.command_metadata.get("profile"))
                if primary.command_metadata.get("profile") is not None
                else None
            ),
            status=primary.status.value,
            provider=primary.provider_name,
            provider_version=primary.provider_version,
            rulesets=[str(item) for item in rulesets] if isinstance(rulesets, list) else [],
            eligible_file_count=primary.eligible_file_count,
            files_analyzed=primary.files_analyzed,
            raw_observation_count=primary.raw_observation_count,
            grouped_finding_count=primary.grouped_finding_count,
            primary_count=primary.primary_count,
            supporting_count=primary.supporting_count,
            informational_count=primary.informational_count,
            suppressed_from_html_count=primary.suppressed_from_html_count,
        )

    def _map_recommendations(
        self,
        recommendations: list[Recommendation],
    ) -> list[LLMRecommendationEvidence]:
        ordered = sorted(
            recommendations,
            key=lambda item: (
                str(getattr(item.priority, "value", item.priority)),
                (item.rule_id or "").lower(),
                item.title.lower(),
            ),
        )[:_MAX_RECOMMENDATIONS]
        mapped: list[LLMRecommendationEvidence] = []
        for recommendation in ordered:
            mapped.append(
                LLMRecommendationEvidence(
                    recommendation_id=recommendation.rule_id or str(recommendation.id),
                    title=self._sanitize_text(recommendation.title) or recommendation.title,
                    priority=self._enum_value(recommendation.priority),
                    category=self._enum_value(recommendation.category),
                    related_finding_ids=[
                        item for item in recommendation.related_finding_ids if item.strip()
                    ],
                    summary=self._sanitize_text(recommendation.description)
                    or recommendation.description,
                )
            )
        return mapped

    def _compact_model(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            payload = value.model_dump(mode="json", exclude_none=True)
        elif isinstance(value, dict):
            payload = value
        else:
            return {}
        return self._compact_dict(payload)

    def _compact_dependencies(self, value: Any) -> dict[str, Any]:
        payload = self._compact_model(value)
        if not payload:
            return {}
        # Prefer counts/summaries over complete dependency inventories.
        allowed = {
            "dependency_count",
            "direct_dependency_count",
            "transitive_dependency_count",
            "outdated_dependency_count",
            "has_lockfile",
            "package_managers",
            "manifest_files",
        }
        compact = {key: payload[key] for key in allowed if key in payload}
        outdated = payload.get("outdated_dependencies")
        if isinstance(outdated, list):
            compact["outdated_dependencies_sample"] = outdated[:_MAX_FACT_LIST_ITEMS]
            compact["outdated_dependency_count"] = compact.get(
                "outdated_dependency_count", len(outdated)
            )
        return compact

    def _compact_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, list):
                compact[key] = value[:_MAX_FACT_LIST_ITEMS]
            elif isinstance(value, dict):
                compact[key] = self._compact_dict(value)
            elif isinstance(value, str):
                sanitized = self._sanitize_text(value)
                if sanitized is not None:
                    compact[key] = sanitized
            else:
                compact[key] = value
        return compact

    def _map_metadata(self, metadata: dict[str, Any]) -> dict[str, str]:
        mapped: dict[str, str] = {}
        for key in sorted(metadata.keys(), key=str.lower):
            if not isinstance(key, str):
                continue
            if self._is_excluded_metadata_key(key):
                continue
            # Prefer first-class fields over duplicating group metadata.
            if key in {
                "group_id",
                "customer_visibility",
                "modernization_relevance",
                "occurrence_count",
                "affected_file_count",
                "mapping_rationale",
                "grouped",
            }:
                continue
            value = metadata[key]
            if value is None or isinstance(value, (dict, list, tuple, set)):
                continue
            text = self._sanitize_text(str(value))
            if text is None:
                continue
            mapped[key] = self._truncate_metadata_value(text)
        return mapped

    def _is_excluded_metadata_key(self, key: str) -> bool:
        normalized = key.strip().lower().replace("-", "_")
        if normalized in _EXCLUDED_METADATA_KEYS:
            return True
        return any(
            token in normalized
            for token in (
                "token",
                "password",
                "secret",
                "credential",
                "askpass",
                "private_key",
                "api_key",
            )
        )

    def _truncate_excerpt(self, value: str | None) -> str | None:
        if value is None:
            return None
        sanitized = self._sanitize_text(value)
        if sanitized is None:
            return None
        limit = self._limits.max_excerpt_characters
        if len(sanitized) <= limit:
            return sanitized
        if limit == 0:
            return ""
        return sanitized[:limit]

    def _truncate_metadata_value(self, value: str) -> str:
        limit = self._limits.max_metadata_value_characters
        if len(value) <= limit:
            return value
        if limit == 0:
            return ""
        return value[:limit]

    def _repository_relative_path(self, path: str) -> str:
        candidate = path.strip().replace("\\", "/")
        if candidate.startswith("./"):
            candidate = candidate[2:]
        if Path(candidate).is_absolute() or _ABSOLUTE_PATH_PATTERN.search(f" {candidate}"):
            return Path(candidate).name or "."
        sanitized = self._sanitize_text(candidate)
        return sanitized or "."

    def _sanitize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._sanitize_text(value)

    def _sanitize_text(self, value: str) -> str | None:
        compact = value.strip()
        if not compact:
            return None
        redacted = self._redactor.redact(compact)
        if _ABSOLUTE_PATH_PATTERN.search(f" {redacted}"):
            return None
        lowered = redacted.lower()
        if any(
            marker in lowered
            for marker in (
                "codestrata-askpass",
                "codestrata-git-auth",
                "git_askpass",
                "token_env",
            )
        ):
            return None
        return redacted

    def _enum_value(self, value: Any) -> str:
        raw = getattr(value, "value", value)
        return str(raw).lower()


__all__ = ["AIContextBudgetError", "LLMAnalysisContextBuilder"]
