"""Deterministic comparison of CodeStrata analysis runs against a prior baseline."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from codestrata.models import (
    AnalysisResult,
    Finding,
    Recommendation,
    Repository,
    RepositoryFacts,
)
from codestrata.models.scan_comparison import (
    ComparedFinding,
    ComparedRecommendation,
    ComparisonSummary,
    FactChange,
    PriorityChange,
    ScanComparison,
    SeverityChange,
)
from codestrata.static_analysis.ordering import external_finding_identity

_REPORT_RUN_DIRECTORY_PATTERN = re.compile(r"^\d{8}-\d{6}$")

_SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_PRIORITY_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

# Identity keys for structured object lists in repository facts.
_OBJECT_LIST_IDENTITIES: dict[str, tuple[str, ...]] = {
    "facts.cicd.pipelines": ("provider", "path"),
}

_OBJECT_LIST_SKIP_FIELDS: dict[str, frozenset[str]] = {
    "facts.cicd.pipelines": frozenset({"metadata"}),
}

_PIPELINE_FIELD_LABELS: dict[str, str] = {
    "build_commands": "build capability",
    "test_commands": "test capability",
    "deployment_commands": "deployment capability",
    "security_commands": "security capability",
    "uses_containers": "containers",
    "uses_matrix_builds": "matrix builds",
    "uses_caching": "caching",
    "uses_artifacts": "artifacts",
    "triggers": "triggers",
    "jobs": "jobs",
    "pipeline_name": "pipeline name",
}

_VERSION_DIFFERENCE_NOTE = "Some differences may result from analyzer or ruleset version changes."

_PROVIDER_VERSION_NOTE = (
    "Static-analysis provider versions changed. Some finding differences may "
    "result from rule-engine changes."
)


class ScanComparisonService:
    """Compare the current analysis result against a prior completed scan."""

    def compare(
        self,
        current: AnalysisResult,
        repository_directory: Path,
        current_run_directory: Path,
        current_timestamp: str | None = None,
    ) -> ScanComparison:
        """Compare the current result to the latest previous valid baseline."""

        resolved_current_timestamp = current_timestamp or current_run_directory.name
        baseline = self.load_baseline(
            repository_directory=repository_directory,
            current_run_directory=current_run_directory,
        )

        if baseline is None:
            return ScanComparison(
                baseline_available=False,
                current_timestamp=resolved_current_timestamp,
                current_analyzer_version=current.analyzer_version,
                current_ruleset_version=current.ruleset_version,
            )

        baseline_result, baseline_timestamp = baseline
        return self.compare_results(
            current=current,
            baseline=baseline_result,
            current_timestamp=resolved_current_timestamp,
            baseline_timestamp=baseline_timestamp,
        )

    def load_baseline(
        self,
        repository_directory: Path,
        current_run_directory: Path,
    ) -> tuple[AnalysisResult, str] | None:
        """Load the newest previous valid baseline for one repository."""

        if not repository_directory.exists():
            return None

        current_resolved = current_run_directory.resolve()

        run_directories = sorted(
            (
                path
                for path in repository_directory.iterdir()
                if path.is_dir()
                and _REPORT_RUN_DIRECTORY_PATTERN.match(path.name)
                and path.resolve() != current_resolved
            ),
            key=lambda path: path.name,
            reverse=True,
        )

        for run_directory in run_directories:
            report_json = run_directory / "report.json"
            if not report_json.is_file():
                continue

            loaded = self._load_baseline_result(report_json)
            if loaded is None:
                continue

            return loaded, run_directory.name

        return None

    def compare_results(
        self,
        current: AnalysisResult,
        baseline: AnalysisResult,
        current_timestamp: str,
        baseline_timestamp: str,
    ) -> ScanComparison:
        """Compare two in-memory analysis results deterministically."""

        new_findings, resolved_findings, unchanged_findings, severity_changes = (
            self._compare_findings(
                current=current.findings,
                baseline=baseline.findings,
            )
        )
        (
            new_recommendations,
            resolved_recommendations,
            unchanged_recommendations,
            priority_changes,
        ) = self._compare_recommendations(
            current=current.recommendations,
            baseline=baseline.recommendations,
        )
        fact_changes = self._compare_facts(
            current=current.facts,
            baseline=baseline.facts,
        )

        baseline_analyzer_version = baseline.analyzer_version
        current_analyzer_version = current.analyzer_version
        baseline_ruleset_version = baseline.ruleset_version
        current_ruleset_version = current.ruleset_version

        notes: list[str] = []
        if (
            baseline_analyzer_version != current_analyzer_version
            or baseline_ruleset_version != current_ruleset_version
        ):
            notes.append(_VERSION_DIFFERENCE_NOTE)

        if self._provider_versions_differ(current=current, baseline=baseline):
            notes.append(_PROVIDER_VERSION_NOTE)

        summary = ComparisonSummary(
            new_findings=len(new_findings),
            resolved_findings=len(resolved_findings),
            worsened_findings=sum(change.direction == "increased" for change in severity_changes),
            improved_findings=sum(change.direction == "decreased" for change in severity_changes),
            new_recommendations=len(new_recommendations),
            resolved_recommendations=len(resolved_recommendations),
            worsened_priorities=sum(change.direction == "increased" for change in priority_changes),
            improved_priorities=sum(change.direction == "decreased" for change in priority_changes),
            fact_changes=len(fact_changes),
        )

        return ScanComparison(
            baseline_available=True,
            baseline_timestamp=baseline_timestamp,
            current_timestamp=current_timestamp,
            baseline_analyzer_version=baseline_analyzer_version,
            current_analyzer_version=current_analyzer_version,
            baseline_ruleset_version=baseline_ruleset_version,
            current_ruleset_version=current_ruleset_version,
            notes=notes,
            new_findings=new_findings,
            resolved_findings=resolved_findings,
            unchanged_findings=unchanged_findings,
            severity_changes=severity_changes,
            new_recommendations=new_recommendations,
            resolved_recommendations=resolved_recommendations,
            unchanged_recommendations=unchanged_recommendations,
            priority_changes=priority_changes,
            fact_changes=fact_changes,
            summary=summary,
        )

    def _load_baseline_result(self, report_json: Path) -> AnalysisResult | None:
        try:
            payload = json.loads(report_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None

        # Avoid recursively comparing prior comparison sections.
        payload.pop("comparison", None)

        try:
            return AnalysisResult.model_validate(payload)
        except Exception:
            return self._load_partial_baseline(payload)

    def _load_partial_baseline(
        self,
        payload: dict[str, Any],
    ) -> AnalysisResult | None:
        """Best-effort baseline loading for older or partial report files."""

        repository_payload = payload.get("repository")
        if not isinstance(repository_payload, dict):
            return None

        name = repository_payload.get("name")
        path = repository_payload.get("path")
        if not isinstance(name, str) or not isinstance(path, str):
            return None

        try:
            findings = [
                Finding.model_validate(item)
                for item in payload.get("findings", [])
                if isinstance(item, dict)
            ]
        except Exception:
            findings = []

        recommendations: list[Recommendation] = []
        for item in payload.get("recommendations", []):
            if not isinstance(item, dict):
                continue
            try:
                recommendations.append(Recommendation.model_validate(item))
            except Exception:
                continue

        facts_payload = payload.get("facts", {})
        try:
            facts = (
                RepositoryFacts.model_validate(facts_payload)
                if isinstance(facts_payload, dict)
                else RepositoryFacts()
            )
        except Exception:
            facts = RepositoryFacts()

        try:
            return AnalysisResult(
                repository=Repository(
                    name=name,
                    path=Path(path),
                    files=[
                        str(item)
                        for item in repository_payload.get("files", [])
                        if isinstance(item, str)
                    ],
                ),
                facts=facts,
                findings=findings,
                recommendations=recommendations,
                analyzer_version=(
                    payload.get("analyzer_version")
                    if isinstance(payload.get("analyzer_version"), str)
                    else None
                ),
                ruleset_version=(
                    payload.get("ruleset_version")
                    if isinstance(payload.get("ruleset_version"), str)
                    else None
                ),
            )
        except Exception:
            return None

    def _compare_findings(
        self,
        current: Sequence[Finding],
        baseline: Sequence[Finding],
    ) -> tuple[
        list[ComparedFinding],
        list[ComparedFinding],
        list[ComparedFinding],
        list[SeverityChange],
    ]:
        current_map = self._finding_identity_map(current)
        baseline_map = self._finding_identity_map(baseline)

        new_findings: list[ComparedFinding] = []
        resolved_findings: list[ComparedFinding] = []
        unchanged_findings: list[ComparedFinding] = []
        severity_changes: list[SeverityChange] = []

        for key in sorted(set(current_map) | set(baseline_map)):
            current_finding = current_map.get(key)
            baseline_finding = baseline_map.get(key)

            if current_finding is not None and baseline_finding is None:
                new_findings.append(self._compared_finding(current_finding, key))
                continue

            if current_finding is None and baseline_finding is not None:
                resolved_findings.append(self._compared_finding(baseline_finding, key))
                continue

            if current_finding is None or baseline_finding is None:
                continue

            current_severity = self._enum_value(current_finding.severity)
            baseline_severity = self._enum_value(baseline_finding.severity)

            if current_severity == baseline_severity:
                unchanged_findings.append(self._compared_finding(current_finding, key))
                continue

            direction = self._rank_direction(
                previous=baseline_severity,
                current=current_severity,
                ranking=_SEVERITY_RANK,
            )
            if direction is None:
                unchanged_findings.append(self._compared_finding(current_finding, key))
                continue

            severity_changes.append(
                SeverityChange(
                    rule_id=current_finding.rule_id,
                    title=current_finding.title,
                    category=self._enum_value(current_finding.category),
                    identity_key=key,
                    previous_severity=baseline_severity,
                    current_severity=current_severity,
                    direction=direction,
                )
            )

        return (
            new_findings,
            resolved_findings,
            unchanged_findings,
            severity_changes,
        )

    def _compare_recommendations(
        self,
        current: Sequence[Recommendation],
        baseline: Sequence[Recommendation],
    ) -> tuple[
        list[ComparedRecommendation],
        list[ComparedRecommendation],
        list[ComparedRecommendation],
        list[PriorityChange],
    ]:
        current_map = {recommendation.rule_id: recommendation for recommendation in current}
        baseline_map = {recommendation.rule_id: recommendation for recommendation in baseline}

        new_recommendations: list[ComparedRecommendation] = []
        resolved_recommendations: list[ComparedRecommendation] = []
        unchanged_recommendations: list[ComparedRecommendation] = []
        priority_changes: list[PriorityChange] = []

        for rule_id in sorted(set(current_map) | set(baseline_map)):
            current_recommendation = current_map.get(rule_id)
            baseline_recommendation = baseline_map.get(rule_id)

            if current_recommendation is not None and baseline_recommendation is None:
                new_recommendations.append(self._compared_recommendation(current_recommendation))
                continue

            if current_recommendation is None and baseline_recommendation is not None:
                resolved_recommendations.append(
                    self._compared_recommendation(baseline_recommendation)
                )
                continue

            if current_recommendation is None or baseline_recommendation is None:
                continue

            current_priority = self._enum_value(current_recommendation.priority)
            baseline_priority = self._enum_value(baseline_recommendation.priority)

            if current_priority == baseline_priority:
                unchanged_recommendations.append(
                    self._compared_recommendation(current_recommendation)
                )
                continue

            direction = self._rank_direction(
                previous=baseline_priority,
                current=current_priority,
                ranking=_PRIORITY_RANK,
            )
            if direction is None:
                unchanged_recommendations.append(
                    self._compared_recommendation(current_recommendation)
                )
                continue

            priority_changes.append(
                PriorityChange(
                    rule_id=rule_id,
                    title=current_recommendation.title,
                    category=self._enum_value(current_recommendation.category),
                    previous_priority=baseline_priority,
                    current_priority=current_priority,
                    direction=direction,
                )
            )

        return (
            new_recommendations,
            resolved_recommendations,
            unchanged_recommendations,
            priority_changes,
        )

    def _compare_facts(
        self,
        current: RepositoryFacts,
        baseline: RepositoryFacts,
    ) -> list[FactChange]:
        current_data = current.model_dump(mode="json")
        baseline_data = baseline.model_dump(mode="json")
        changes: list[FactChange] = []
        self._compare_fact_nodes(
            path="facts",
            previous=baseline_data,
            current=current_data,
            changes=changes,
        )
        return sorted(changes, key=lambda change: change.path)

    def _compare_fact_nodes(
        self,
        path: str,
        previous: Any,
        current: Any,
        changes: list[FactChange],
    ) -> None:
        if previous is None and current is None:
            return

        if isinstance(previous, Mapping) and isinstance(current, Mapping):
            keys = sorted(set(previous) | set(current))
            for key in keys:
                child_path = f"{path}.{key}" if path else str(key)
                self._compare_fact_nodes(
                    path=child_path,
                    previous=previous.get(key),
                    current=current.get(key),
                    changes=changes,
                )
            return

        if isinstance(previous, list) and isinstance(current, list):
            if self._is_structured_object_list(path, previous, current):
                self._compare_structured_object_list(
                    path=path,
                    previous=previous,
                    current=current,
                    changes=changes,
                )
                return

            previous_values = [self._stringify(item) for item in previous]
            current_values = [self._stringify(item) for item in current]

            if Counter(previous_values) == Counter(current_values):
                return

            previous_set = list(dict.fromkeys(previous_values))
            current_set = list(dict.fromkeys(current_values))
            added = [value for value in current_set if value not in previous_set]
            removed = [value for value in previous_set if value not in current_set]

            if not added and not removed:
                return

            changes.append(
                FactChange(
                    path=path,
                    change_type="changed",
                    previous_value=previous_values,
                    current_value=current_values,
                    added_values=added,
                    removed_values=removed,
                    summary=(f"{path}: added=[{', '.join(added)}]; removed=[{', '.join(removed)}]"),
                )
            )
            return

        if previous is None and isinstance(current, list) and path in _OBJECT_LIST_IDENTITIES:
            self._compare_structured_object_list(
                path=path,
                previous=[],
                current=current,
                changes=changes,
            )
            return

        if current is None and isinstance(previous, list) and path in _OBJECT_LIST_IDENTITIES:
            self._compare_structured_object_list(
                path=path,
                previous=previous,
                current=[],
                changes=changes,
            )
            return

        if previous == current:
            return

        if previous is None:
            changes.append(
                FactChange(
                    path=path,
                    change_type="added",
                    current_value=current,
                    summary=f"{path}: added {self._display_scalar(current)}",
                )
            )
            return

        if current is None:
            changes.append(
                FactChange(
                    path=path,
                    change_type="removed",
                    previous_value=previous,
                    summary=f"{path}: removed {self._display_scalar(previous)}",
                )
            )
            return

        changes.append(
            FactChange(
                path=path,
                change_type="changed",
                previous_value=previous,
                current_value=current,
                summary=(
                    f"{path}: {self._display_scalar(previous)} → {self._display_scalar(current)}"
                ),
            )
        )

    def _is_structured_object_list(
        self,
        path: str,
        previous: list[Any],
        current: list[Any],
    ) -> bool:
        if path not in _OBJECT_LIST_IDENTITIES:
            return False

        values = [*previous, *current]
        if not values:
            return True

        return all(isinstance(item, Mapping) for item in values)

    def _compare_structured_object_list(
        self,
        path: str,
        previous: list[Any],
        current: list[Any],
        changes: list[FactChange],
    ) -> None:
        identity_keys = _OBJECT_LIST_IDENTITIES[path]
        skip_fields = _OBJECT_LIST_SKIP_FIELDS.get(path, frozenset())

        previous_map = self._object_identity_map(previous, identity_keys)
        current_map = self._object_identity_map(current, identity_keys)

        for identity in sorted(set(previous_map) | set(current_map)):
            previous_item = previous_map.get(identity)
            current_item = current_map.get(identity)
            label = self._object_identity_label(identity, identity_keys)

            if previous_item is None and current_item is not None:
                provider = str(current_item.get("provider", "unknown"))
                item_path = str(current_item.get("path", identity))
                changes.append(
                    FactChange(
                        path=f"{path}[{identity}]",
                        change_type="added",
                        current_value={key: current_item.get(key) for key in identity_keys},
                        summary=f"Added pipeline {item_path} ({provider})",
                    )
                )
                continue

            if previous_item is not None and current_item is None:
                provider = str(previous_item.get("provider", "unknown"))
                item_path = str(previous_item.get("path", identity))
                changes.append(
                    FactChange(
                        path=f"{path}[{identity}]",
                        change_type="removed",
                        previous_value={key: previous_item.get(key) for key in identity_keys},
                        summary=f"Removed pipeline {item_path} ({provider})",
                    )
                )
                continue

            if previous_item is None or current_item is None:
                continue

            field_names = sorted((set(previous_item) | set(current_item)) - set(skip_fields))
            for field_name in field_names:
                previous_value = previous_item.get(field_name)
                current_value = current_item.get(field_name)
                if previous_value == current_value:
                    continue

                if isinstance(previous_value, list) and isinstance(current_value, list):
                    if Counter(map(self._stringify, previous_value)) == Counter(
                        map(self._stringify, current_value)
                    ):
                        continue

                field_path = f"{path}[{identity}].{field_name}"
                summary = self._structured_field_summary(
                    object_label=label,
                    field_name=field_name,
                    previous_value=previous_value,
                    current_value=current_value,
                )
                changes.append(
                    FactChange(
                        path=field_path,
                        change_type="changed",
                        previous_value=previous_value,
                        current_value=current_value,
                        summary=summary,
                    )
                )

    def _object_identity_map(
        self,
        items: list[Any],
        identity_keys: tuple[str, ...],
    ) -> dict[str, Mapping[str, Any]]:
        identity_map: dict[str, Mapping[str, Any]] = {}
        for item in items:
            if not isinstance(item, Mapping):
                continue
            identity = "|".join(str(item.get(key, "")) for key in identity_keys)
            identity_map[identity] = item
        return identity_map

    @staticmethod
    def _object_identity_label(
        identity: str,
        identity_keys: tuple[str, ...],
    ) -> str:
        parts = identity.split("|", maxsplit=len(identity_keys) - 1)
        if "path" in identity_keys:
            path_index = identity_keys.index("path")
            if path_index < len(parts) and parts[path_index]:
                return parts[path_index]
        return identity

    def _structured_field_summary(
        self,
        *,
        object_label: str,
        field_name: str,
        previous_value: Any,
        current_value: Any,
    ) -> str:
        field_label = _PIPELINE_FIELD_LABELS.get(field_name, field_name.replace("_", " "))

        if field_name in {
            "build_commands",
            "test_commands",
            "deployment_commands",
            "security_commands",
        }:
            return (
                f"{object_label}: {field_label} "
                f"{self._capability_flag(previous_value)} → "
                f"{self._capability_flag(current_value)}"
            )

        if isinstance(previous_value, bool) or isinstance(current_value, bool):
            return (
                f"{object_label}: {field_label} "
                f"{self._capability_flag(previous_value)} → "
                f"{self._capability_flag(current_value)}"
            )

        return (
            f"{object_label}: {field_label} "
            f"{self._display_scalar(previous_value)} → "
            f"{self._display_scalar(current_value)}"
        )

    @staticmethod
    def _capability_flag(value: Any) -> str:
        if isinstance(value, list):
            return "Yes" if value else "No"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if value in (None, "", 0):
            return "No"
        return "Yes"

    @staticmethod
    def _display_scalar(value: Any) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, Mapping):
            return "{…}"
        if isinstance(value, list):
            return "[" + ", ".join(str(item) for item in value) + "]"
        return str(value)

    def _finding_identity_map(
        self,
        findings: Sequence[Finding],
    ) -> dict[str, Finding]:
        rule_counts = Counter(finding.rule_id or "" for finding in findings)
        identity_map: dict[str, Finding] = {}

        for finding in findings:
            external_key = external_finding_identity(finding)
            if external_key is not None:
                identity_map[external_key] = finding
                continue

            rule_id = finding.rule_id or ""
            if rule_id and rule_counts[rule_id] == 1:
                key = f"rule:{rule_id}"
            else:
                key = self._duplicate_finding_key(finding)
            identity_map[key] = finding

        return identity_map

    @staticmethod
    def _provider_versions_differ(
        *,
        current: AnalysisResult,
        baseline: AnalysisResult,
    ) -> bool:
        current_versions = {
            result.provider_id: result.provider_version
            for result in current.static_analysis_results
        }
        baseline_versions = {
            result.provider_id: result.provider_version
            for result in baseline.static_analysis_results
        }
        provider_ids = set(current_versions) | set(baseline_versions)
        return any(
            current_versions.get(provider_id) != baseline_versions.get(provider_id)
            for provider_id in provider_ids
        )

    def _duplicate_finding_key(self, finding: Finding) -> str:
        evidence_parts = [
            "|".join(
                [
                    evidence.file_path,
                    str(evidence.line_number or ""),
                    evidence.description or "",
                    evidence.detected_value or "",
                ]
            )
            for evidence in finding.evidence
        ]
        evidence_parts.sort()
        return (
            "dup:"
            f"{finding.rule_id or ''}|"
            f"{self._enum_value(finding.category)}|"
            f"{finding.title}|"
            f"{';'.join(evidence_parts)}"
        )

    def _compared_finding(
        self,
        finding: Finding,
        identity_key: str,
    ) -> ComparedFinding:
        return ComparedFinding(
            rule_id=finding.rule_id,
            title=finding.title,
            category=self._enum_value(finding.category),
            severity=self._enum_value(finding.severity),
            identity_key=identity_key,
        )

    def _compared_recommendation(
        self,
        recommendation: Recommendation,
    ) -> ComparedRecommendation:
        return ComparedRecommendation(
            rule_id=recommendation.rule_id,
            title=recommendation.title,
            priority=self._enum_value(recommendation.priority),
            category=self._enum_value(recommendation.category),
        )

    @staticmethod
    def _rank_direction(
        previous: str,
        current: str,
        ranking: Mapping[str, int],
    ) -> Literal["increased", "decreased"] | None:
        previous_rank = ranking.get(previous.lower())
        current_rank = ranking.get(current.lower())

        if previous_rank is None or current_rank is None:
            return None

        if current_rank > previous_rank:
            return "increased"

        if current_rank < previous_rank:
            return "decreased"

        return None

    @staticmethod
    def _enum_value(value: Any) -> str:
        raw_value = getattr(value, "value", value)
        return str(raw_value).lower()

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, Mapping):
            return json.dumps(value, sort_keys=True, default=str)
        return str(value)
