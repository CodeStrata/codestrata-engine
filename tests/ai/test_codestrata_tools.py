"""Tests for the provider-neutral CodeStrata tool layer."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMEvidenceLocation,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
    LLMTechnologyEvidence,
)
from codestrata.ai.tools import (
    CodeStrataTool,
    CodeStrataToolDefinition,
    CodeStrataToolInputError,
    CodeStrataToolRegistry,
    CodeStrataToolResult,
    EmptyToolInput,
    ListFindingsInput,
    ListFindingsOutput,
    build_analysis_tool_registry,
)
from codestrata.ai.tools.base import CodeStrataToolExecutionError
from codestrata.ai.tools.models import RepositoryContextOutput


def _truncation(
    *, count: int = 0, truncated: bool = False, original: int | None = None
) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=truncated,
        original_count=original if original is not None else count,
        included_count=count,
    )


def _finding(
    *,
    rule_id: str,
    title: str,
    severity: str,
    category: str = "security",
    evidence: list[LLMEvidenceLocation] | None = None,
) -> LLMFindingEvidence:
    locations = evidence or []
    return LLMFindingEvidence(
        rule_id=rule_id,
        title=title,
        category=category,
        severity=severity,
        summary=f"Summary for {rule_id}",
        evidence=locations,
        evidence_truncation=_truncation(count=len(locations)),
    )


def _sample_context() -> LLMAnalysisContext:
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="sample-app",
            source_type="github",
            default_branch="main",
            commit_sha="abc1234",
            file_count=12,
        ),
        technologies=[
            LLMTechnologyEvidence(
                name="Java",
                category="language",
                version="17",
                confidence=0.95,
                evidence=["pom.xml"],
            ),
            LLMTechnologyEvidence(
                name="Maven",
                category="build_tool",
                evidence=["pom.xml"],
            ),
        ],
        metrics=LLMMetricsContext(
            file_count=12,
            source_file_count=8,
            test_file_count=2,
            finding_count=4,
            technology_count=2,
        ),
        findings=[
            _finding(
                rule_id="SEC002",
                title="Medium finding",
                severity="medium",
                evidence=[LLMEvidenceLocation(path="b/File.java", line=20)],
            ),
            _finding(
                rule_id="SEC001",
                title="Critical finding",
                severity="critical",
                evidence=[LLMEvidenceLocation(path=".")],
            ),
            _finding(
                rule_id="ARCH001",
                title="Architecture finding",
                severity="info",
                category="architecture",
            ),
            _finding(
                rule_id="SEC001",
                title="Critical finding duplicate",
                severity="critical",
                evidence=[
                    LLMEvidenceLocation(path="a/File.java", line=10, column=4),
                    LLMEvidenceLocation(path="c/File.java", line=3),
                ],
            ),
        ],
        findings_truncation=_truncation(count=4, truncated=True, original=6),
    )


class _EchoTool(CodeStrataTool[EmptyToolInput, RepositoryContextOutput]):
    name = "echo_repo"
    description = "Echo repository context for registry tests."
    input_model = EmptyToolInput
    output_model = RepositoryContextOutput

    def __init__(self, context: LLMAnalysisContext) -> None:
        self._context = context

    def run(self, payload: EmptyToolInput) -> RepositoryContextOutput:
        del payload
        return RepositoryContextOutput(repository=self._context.repository)


class _BoomTool(CodeStrataTool[EmptyToolInput, ListFindingsOutput]):
    name = "boom"
    description = "Raises a raw exception."
    input_model = EmptyToolInput
    output_model = ListFindingsOutput

    def run(self, payload: EmptyToolInput) -> ListFindingsOutput:
        del payload
        raise RuntimeError("unexpected boom")


class _NamedTool(CodeStrataTool[EmptyToolInput, ListFindingsOutput]):
    input_model = EmptyToolInput
    output_model = ListFindingsOutput

    def __init__(self, name: str) -> None:
        self.name = name
        self.description = f"Tool {name}"

    def run(self, payload: EmptyToolInput) -> ListFindingsOutput:
        del payload
        return ListFindingsOutput(
            findings=[],
            total_matched=0,
            returned=0,
            truncated=False,
        )


def test_register_and_list_definitions_in_stable_order() -> None:
    registry = CodeStrataToolRegistry()
    registry.register(_NamedTool("zeta"))
    registry.register(_NamedTool("alpha"))
    registry.register(_NamedTool("Beta"))

    names = registry.list_names()
    assert names == ["alpha", "Beta", "zeta"]
    definitions = registry.list_definitions()
    assert [item.name for item in definitions] == names
    assert all(isinstance(item, CodeStrataToolDefinition) for item in definitions)


def test_duplicate_tool_rejection_is_case_insensitive() -> None:
    registry = CodeStrataToolRegistry()
    registry.register(_NamedTool("ListFindings"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_NamedTool("listfindings"))


def test_case_insensitive_lookup() -> None:
    context = _sample_context()
    registry = CodeStrataToolRegistry()
    tool = _EchoTool(context)
    registry.register(tool)

    assert registry.has("ECHO_REPO")
    assert registry.get("echo_repo") is tool
    assert registry.get("Echo_Repo") is tool


def test_unknown_tool_execute_returns_error_result() -> None:
    registry = CodeStrataToolRegistry()
    result = registry.execute("missing_tool", {})
    assert isinstance(result, CodeStrataToolResult)
    assert result.success is False
    assert result.data is None
    assert result.error == "Unknown tool: missing_tool"
    assert result.tool_name == "missing_tool"


def test_unknown_tool_get_raises() -> None:
    registry = CodeStrataToolRegistry()
    with pytest.raises(KeyError, match="Unknown tool"):
        registry.get("nope")


def test_valid_tool_execution_via_registry() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("get_repository_context", {})
    assert result.success is True
    assert result.error is None
    assert result.tool_name == "get_repository_context"
    assert result.data is not None
    assert result.data["repository"]["name"] == "sample-app"


def test_invalid_input_handling() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("list_findings", {"limit": 0})
    assert result.success is False
    assert result.data is None
    assert result.error is not None
    assert "Invalid input" in result.error


def test_invalid_input_extra_fields_forbidden() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("list_findings", {"severity": "high", "extra": True})
    assert result.success is False
    assert result.error is not None
    assert "Invalid input" in result.error


def test_raw_exception_containment_via_registry() -> None:
    registry = CodeStrataToolRegistry()
    registry.register(_BoomTool())
    result = registry.execute("boom", {})
    assert result.success is False
    assert result.data is None
    assert result.error == "Tool 'boom' failed during execution."
    assert "unexpected boom" not in (result.error or "")


def test_raw_exception_containment_via_tool_execute() -> None:
    tool = _BoomTool()
    with pytest.raises(CodeStrataToolExecutionError, match="failed during execution"):
        tool.execute({})


def test_get_repository_context() -> None:
    context = _sample_context()
    registry = build_analysis_tool_registry(context)
    result = registry.execute("get_repository_context")
    assert result.success is True
    assert result.data == {
        "repository": {
            "name": "sample-app",
            "source_type": "github",
            "default_branch": "main",
            "commit_sha": "abc1234",
            "file_count": 12,
        }
    }


def test_list_technologies() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("list_technologies", {})
    assert result.success is True
    assert result.data is not None
    assert result.data["count"] == 2
    names = [item["name"] for item in result.data["technologies"]]
    assert names == ["Java", "Maven"]


def test_get_repository_metrics() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("get_repository_metrics")
    assert result.success is True
    assert result.data == {
        "metrics": {
            "file_count": 12,
            "source_file_count": 8,
            "test_file_count": 2,
            "finding_count": 4,
            "technology_count": 2,
            "recommendation_count": 0,
        }
    }


def test_list_findings_filters_and_stable_order() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute(
        "list_findings",
        {"severity": "CRITICAL", "category": "Security"},
    )
    assert result.success is True
    assert result.data is not None
    findings = result.data["findings"]
    assert result.data["total_matched"] == 2
    assert result.data["returned"] == 2
    assert result.data["truncated"] is False
    titles = [item["title"] for item in findings]
    assert titles == ["Critical finding", "Critical finding duplicate"]


def test_list_findings_rule_id_filter() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("list_findings", {"rule_id": "arch001"})
    assert result.success is True
    assert result.data is not None
    assert result.data["total_matched"] == 1
    assert result.data["findings"][0]["rule_id"] == "ARCH001"


def test_list_findings_result_limit() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("list_findings", {"limit": 2})
    assert result.success is True
    assert result.data is not None
    assert result.data["total_matched"] == 4
    assert result.data["returned"] == 2
    assert result.data["truncated"] is True
    assert len(result.data["findings"]) == 2


def test_get_finding_details() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("get_finding_details", {"rule_id": "sec001"})
    assert result.success is True
    assert result.data is not None
    assert result.data["found"] is True
    assert result.data["rule_id"] == "sec001"
    assert len(result.data["findings"]) == 2
    evidence_counts = [len(item["evidence"]) for item in result.data["findings"]]
    assert evidence_counts == [1, 2]


def test_get_finding_details_not_found() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("get_finding_details", {"rule_id": "MISSING"})
    assert result.success is True
    assert result.data is not None
    assert result.data["found"] is False
    assert result.data["findings"] == []


def test_get_evidence_coverage() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("get_evidence_coverage")
    assert result.success is True
    assert result.data == {
        "finding_count": 4,
        "findings_included": 4,
        "findings_original_count": 6,
        "findings_truncated": True,
        "findings_with_evidence": 3,
        "total_evidence_locations": 4,
    }


def test_get_llm_analysis_context() -> None:
    context = _sample_context()
    registry = build_analysis_tool_registry(context)
    result = registry.execute("GET_LLM_ANALYSIS_CONTEXT")
    assert result.success is True
    assert result.data is not None
    assert result.data["context"] == context.model_dump(mode="json")


def test_analysis_registry_lists_expected_tools() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    assert registry.list_names() == [
        "get_evidence_coverage",
        "get_finding_details",
        "get_llm_analysis_context",
        "get_repository_context",
        "get_repository_metrics",
        "list_findings",
        "list_technologies",
    ]


def test_deterministic_output() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    first = registry.execute("list_findings", {"limit": 3})
    second = registry.execute("list_findings", {"limit": 3})
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_immutable_contracts() -> None:
    definition = CodeStrataToolDefinition(
        name="demo",
        description="Demo tool",
        input_model="EmptyToolInput",
        output_model="ListFindingsOutput",
    )
    result = CodeStrataToolResult(tool_name="demo", success=True, data={}, error=None)
    payload = ListFindingsInput(severity="high", limit=1)

    with pytest.raises(ValidationError):
        definition.name = "other"
    with pytest.raises(ValidationError):
        result.success = False
    with pytest.raises(ValidationError):
        payload.limit = 5


def test_tool_input_validation_raises_typed_error() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    tool = registry.get("list_findings")
    with pytest.raises(CodeStrataToolInputError, match="Invalid input"):
        tool.validate_input({"limit": -1})


def test_empty_input_defaults() -> None:
    registry = build_analysis_tool_registry(_sample_context())
    result = registry.execute("list_technologies", None)
    assert result.success is True
    assert result.data is not None
    assert result.data["count"] == 2
