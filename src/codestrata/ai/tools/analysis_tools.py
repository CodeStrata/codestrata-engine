"""Read-only analysis tools operating on LLMAnalysisContext."""

from __future__ import annotations

from codestrata.ai.contracts.models import LLMAnalysisContext, LLMFindingEvidence
from codestrata.ai.tools.base import CodeStrataTool
from codestrata.ai.tools.models import (
    AnalysisEvidenceCoverageOutput,
    EmptyToolInput,
    GetFindingDetailsInput,
    GetFindingDetailsOutput,
    ListFindingsInput,
    ListFindingsOutput,
    LLMAnalysisContextOutput,
    MetricsOutput,
    RepositoryContextOutput,
    TechnologiesOutput,
)
from codestrata.ai.tools.registry import CodeStrataToolRegistry


def _normalize_filter(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip().lower()
    return compact or None


def _finding_sort_key(finding: LLMFindingEvidence) -> tuple[str, str, str, str]:
    return (
        (finding.severity or "").lower(),
        (finding.category or "").lower(),
        (finding.rule_id or "").lower(),
        (finding.title or "").lower(),
    )


class GetRepositoryContextTool(CodeStrataTool[EmptyToolInput, RepositoryContextOutput]):
    """Return repository details from an LLMAnalysisContext."""

    name = "get_repository_context"
    description = "Return repository identity and inventory details."
    input_model = EmptyToolInput
    output_model = RepositoryContextOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: EmptyToolInput) -> RepositoryContextOutput:
        del payload
        return RepositoryContextOutput(repository=self._context.repository)


class ListTechnologiesTool(CodeStrataTool[EmptyToolInput, TechnologiesOutput]):
    """Return detected technology evidence."""

    name = "list_technologies"
    description = "Return detected technologies in stable order."
    input_model = EmptyToolInput
    output_model = TechnologiesOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: EmptyToolInput) -> TechnologiesOutput:
        del payload
        technologies = list(self._context.technologies)
        return TechnologiesOutput(technologies=technologies, count=len(technologies))


class GetRepositoryMetricsTool(CodeStrataTool[EmptyToolInput, MetricsOutput]):
    """Return repository metrics."""

    name = "get_repository_metrics"
    description = "Return repository metrics from the analysis context."
    input_model = EmptyToolInput
    output_model = MetricsOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: EmptyToolInput) -> MetricsOutput:
        del payload
        return MetricsOutput(metrics=self._context.metrics)


class ListFindingsTool(CodeStrataTool[ListFindingsInput, ListFindingsOutput]):
    """List findings with optional filters and result limit."""

    name = "list_findings"
    description = "List findings with optional severity, category, and rule_id filters."
    input_model = ListFindingsInput
    output_model = ListFindingsOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: ListFindingsInput) -> ListFindingsOutput:
        severity = _normalize_filter(payload.severity)
        category = _normalize_filter(payload.category)
        rule_id = _normalize_filter(payload.rule_id)

        matched = [
            finding
            for finding in self._context.findings
            if (severity is None or (finding.severity or "").lower() == severity)
            and (category is None or (finding.category or "").lower() == category)
            and (rule_id is None or (finding.rule_id or "").lower() == rule_id)
        ]
        ordered = sorted(matched, key=_finding_sort_key)
        total_matched = len(ordered)
        if payload.limit is None:
            selected = ordered
        else:
            selected = ordered[: payload.limit]

        return ListFindingsOutput(
            findings=selected,
            total_matched=total_matched,
            returned=len(selected),
            truncated=total_matched > len(selected),
        )


class GetFindingDetailsTool(CodeStrataTool[GetFindingDetailsInput, GetFindingDetailsOutput]):
    """Return all findings matching a rule_id."""

    name = "get_finding_details"
    description = "Return all findings and evidence for a rule_id."
    input_model = GetFindingDetailsInput
    output_model = GetFindingDetailsOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: GetFindingDetailsInput) -> GetFindingDetailsOutput:
        target = payload.rule_id.strip().lower()
        matched = [
            finding
            for finding in self._context.findings
            if (finding.rule_id or "").lower() == target
        ]
        ordered = sorted(matched, key=_finding_sort_key)
        return GetFindingDetailsOutput(
            rule_id=payload.rule_id.strip(),
            findings=ordered,
            found=bool(ordered),
        )


class GetEvidenceCoverageTool(CodeStrataTool[EmptyToolInput, AnalysisEvidenceCoverageOutput]):
    """Return finding counts, truncation state, and evidence availability."""

    name = "get_evidence_coverage"
    description = "Return finding counts, truncation state, and evidence availability."
    input_model = EmptyToolInput
    output_model = AnalysisEvidenceCoverageOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: EmptyToolInput) -> AnalysisEvidenceCoverageOutput:
        del payload
        findings = self._context.findings
        findings_with_evidence = sum(1 for item in findings if item.evidence)
        total_evidence_locations = sum(len(item.evidence) for item in findings)
        truncation = self._context.findings_truncation
        return AnalysisEvidenceCoverageOutput(
            finding_count=len(findings),
            findings_included=truncation.included_count,
            findings_original_count=truncation.original_count,
            findings_truncated=truncation.truncated,
            findings_with_evidence=findings_with_evidence,
            total_evidence_locations=total_evidence_locations,
        )


class GetLLMAnalysisContextTool(CodeStrataTool[EmptyToolInput, LLMAnalysisContextOutput]):
    """Return the complete LLMAnalysisContext."""

    name = "get_llm_analysis_context"
    description = "Return the complete serialized LLMAnalysisContext."
    input_model = EmptyToolInput
    output_model = LLMAnalysisContextOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: EmptyToolInput) -> LLMAnalysisContextOutput:
        del payload
        return LLMAnalysisContextOutput(context=self._context)


def build_analysis_tool_registry(context: LLMAnalysisContext) -> CodeStrataToolRegistry:
    """Create a registry populated with read-only analysis tools."""

    registry = CodeStrataToolRegistry()
    registry.register_many(
        [
            GetRepositoryContextTool(context),
            ListTechnologiesTool(context),
            GetRepositoryMetricsTool(context),
            ListFindingsTool(context),
            GetFindingDetailsTool(context),
            GetEvidenceCoverageTool(context),
            GetLLMAnalysisContextTool(context),
        ]
    )
    return registry
