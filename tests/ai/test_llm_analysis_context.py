"""Tests for the LLM evidence contract builder and serialization."""

from __future__ import annotations

from pathlib import Path

from codestrata.ai.contracts import (
    LLMAnalysisContextBuilder,
    LLMContractLimits,
    llm_context_from_json,
    llm_context_to_json,
)
from codestrata.models import (
    AnalysisResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
)


def _tech(name: str, category: TechnologyCategory, *, version: str | None = None) -> Technology:
    return Technology(
        name=name,
        category=category,
        version=version,
        confidence=0.9,
        source="detector",
    )


def _finding(
    *,
    rule_id: str,
    title: str,
    severity: Severity,
    category: FindingCategory = FindingCategory.SECURITY,
    evidence: list[Evidence] | None = None,
    affected: list[str] | None = None,
    metadata: dict[str, object] | None = None,
    description: str = "Finding summary",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        title=title,
        description=description,
        category=category,
        severity=severity,
        source=FindingSource.DETERMINISTIC,
        evidence=evidence or [],
        affected_technologies=affected or [],
        metadata=metadata or {},
    )


def _complete_result(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "workspace" / "sample-app",
            source_url="https://github.com/example/sample-app.git",
            default_branch="main",
            files=["pom.xml", "src/App.java"],
            total_files=2,
            metadata={"commit_sha": "abc1234"},
        ),
        technologies=[
            _tech("Spring Boot", TechnologyCategory.FRAMEWORK, version="3.1.0"),
            _tech("Java", TechnologyCategory.LANGUAGE, version="17"),
            _tech("Maven", TechnologyCategory.BUILD_TOOL),
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=2,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[
            _finding(
                rule_id="SEC002",
                title="Medium finding",
                severity=Severity.MEDIUM,
                evidence=[
                    Evidence(file_path="b/File.java", line_number=20),
                    Evidence(file_path="a/File.java", line_number=10, column_number=4),
                ],
                affected=["Java", "Spring Boot"],
                metadata={"provider_name": "native", "ruleset": "security"},
            ),
            _finding(
                rule_id="SEC001",
                title="Critical finding",
                severity=Severity.CRITICAL,
                evidence=[Evidence(file_path=".", description="Whole repository")],
                affected=["Java"],
            ),
            _finding(
                rule_id="ARCH001",
                title="Info finding",
                severity=Severity.INFO,
                category=FindingCategory.ARCHITECTURE,
                evidence=[
                    Evidence(
                        file_path="src/App.java",
                        line_number=3,
                        column_number=1,
                        snippet="class App {}",
                    )
                ],
            ),
        ],
    )


def test_complete_analysis_result_mapping(tmp_path: Path) -> None:
    context = LLMAnalysisContextBuilder().build(_complete_result(tmp_path))

    assert context.schema_version == "1.1.0"
    assert context.repository.name == "sample-app"
    assert context.repository.source_type == "github"
    assert context.repository.default_branch == "main"
    assert context.repository.commit_sha == "abc1234"
    assert context.repository.file_count == 2
    assert context.metrics.finding_count == 3
    assert context.metrics.technology_count == 3
    assert context.findings_truncation.truncated is False
    assert context.findings_truncation.original_count == 3
    assert context.findings_truncation.included_count == 3
    assert len(context.findings) == 3
    assert len(context.technologies) == 3


def test_empty_analysis_result(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="empty", path=tmp_path, files=[]),
    )
    context = LLMAnalysisContextBuilder().build(result)

    assert context.repository.source_type == "local"
    assert context.technologies == []
    assert context.findings == []
    assert context.metrics.finding_count == 0
    assert context.findings_truncation.original_count == 0
    assert context.findings_truncation.included_count == 0
    assert context.findings_truncation.truncated is False


def test_deterministic_json_output(tmp_path: Path) -> None:
    builder = LLMAnalysisContextBuilder()
    result = _complete_result(tmp_path)
    first = llm_context_to_json(builder.build(result))
    second = llm_context_to_json(builder.build(result))
    assert first == second


def test_findings_ordering(tmp_path: Path) -> None:
    context = LLMAnalysisContextBuilder().build(_complete_result(tmp_path))
    assert [item.rule_id for item in context.findings] == [
        "SEC001",
        "SEC002",
        "ARCH001",
    ]


def test_technology_ordering(tmp_path: Path) -> None:
    context = LLMAnalysisContextBuilder().build(_complete_result(tmp_path))
    assert [item.name for item in context.technologies] == [
        "Maven",
        "Spring Boot",
        "Java",
    ]
    assert [item.category for item in context.technologies] == [
        "build_tool",
        "framework",
        "language",
    ]


def test_evidence_ordering(tmp_path: Path) -> None:
    context = LLMAnalysisContextBuilder().build(_complete_result(tmp_path))
    medium = next(item for item in context.findings if item.rule_id == "SEC002")
    assert [item.path for item in medium.evidence] == ["a/File.java", "b/File.java"]
    assert medium.evidence[0].line == 10
    assert medium.evidence[0].column == 4


def test_repository_root_evidence_preserved(tmp_path: Path) -> None:
    context = LLMAnalysisContextBuilder().build(_complete_result(tmp_path))
    critical = next(item for item in context.findings if item.rule_id == "SEC001")
    assert critical.evidence[0].path == "."


def test_normal_path_line_and_column(tmp_path: Path) -> None:
    context = LLMAnalysisContextBuilder().build(_complete_result(tmp_path))
    info = next(item for item in context.findings if item.rule_id == "ARCH001")
    assert info.evidence[0].path == "src/App.java"
    assert info.evidence[0].line == 3
    assert info.evidence[0].column == 1
    assert info.evidence[0].excerpt == "class App {}"


def test_excerpt_truncation(tmp_path: Path) -> None:
    long_snippet = "x" * 50
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            _finding(
                rule_id="SEC001",
                title="Long excerpt",
                severity=Severity.LOW,
                evidence=[Evidence(file_path="a.java", snippet=long_snippet)],
            )
        ],
    )
    context = LLMAnalysisContextBuilder(limits=LLMContractLimits(max_excerpt_characters=10)).build(
        result
    )
    assert context.findings[0].evidence[0].excerpt == "x" * 10


def test_finding_limit_truncation(tmp_path: Path) -> None:
    findings = [
        _finding(
            rule_id=f"R{index:03d}",
            title=f"Finding {index}",
            severity=Severity.LOW,
        )
        for index in range(5)
    ]
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=findings,
    )
    context = LLMAnalysisContextBuilder(limits=LLMContractLimits(max_findings=2)).build(result)
    assert len(context.findings) == 2
    assert context.findings_truncation.truncated is True
    assert context.findings_truncation.original_count == 5
    assert context.findings_truncation.included_count == 2


def test_evidence_limit_truncation(tmp_path: Path) -> None:
    evidence = [Evidence(file_path=f"f{index}.java", line_number=index + 1) for index in range(5)]
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            _finding(
                rule_id="SEC001",
                title="Many evidence",
                severity=Severity.MEDIUM,
                evidence=evidence,
            )
        ],
    )
    context = LLMAnalysisContextBuilder(limits=LLMContractLimits(max_evidence_per_finding=2)).build(
        result
    )
    finding = context.findings[0]
    assert len(finding.evidence) == 2
    assert finding.evidence_truncation.truncated is True
    assert finding.evidence_truncation.original_count == 5
    assert finding.evidence_truncation.included_count == 2


def test_metadata_truncation(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            _finding(
                rule_id="SEC001",
                title="Meta",
                severity=Severity.LOW,
                metadata={"note": "abcdefghij"},
            )
        ],
    )
    context = LLMAnalysisContextBuilder(
        limits=LLMContractLimits(max_metadata_value_characters=4)
    ).build(result)
    assert context.findings[0].metadata["note"] == "abcd"


def test_secret_leakage_prevention(tmp_path: Path) -> None:
    token = "ghp_" + ("a" * 36)
    result = AnalysisResult(
        repository=Repository(name="sample", path=tmp_path, files=[]),
        findings=[
            _finding(
                rule_id="SEC001",
                title="Secret",
                severity=Severity.HIGH,
                description=f"Detected {token}",
                evidence=[Evidence(file_path="a.env", snippet=f"TOKEN={token}")],
                metadata={"token": token, "provider_name": "pmd"},
            )
        ],
    )
    context = LLMAnalysisContextBuilder().build(result)
    payload = llm_context_to_json(context)
    assert token not in payload
    assert "token" not in context.findings[0].metadata
    assert context.findings[0].metadata["provider_name"] == "pmd"
    assert "[REDACTED]" in (context.findings[0].summary or "")


def test_absolute_path_prevention(tmp_path: Path) -> None:
    absolute = str(tmp_path / "secret" / "App.java")
    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=tmp_path / "workspace" / "sample",
            files=[],
        ),
        findings=[
            _finding(
                rule_id="SEC001",
                title="Abs",
                severity=Severity.LOW,
                evidence=[Evidence(file_path=absolute, line_number=1)],
                metadata={"workspace": str(tmp_path), "ok": "relative"},
            )
        ],
    )
    context = LLMAnalysisContextBuilder().build(result)
    payload = llm_context_to_json(context)
    assert str(tmp_path) not in payload
    assert context.findings[0].evidence[0].path == "App.java"
    assert "workspace" not in context.findings[0].metadata
    assert context.findings[0].metadata["ok"] == "relative"


def test_private_github_authentication_data_excluded(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(
            name="private-app",
            path=tmp_path / ".codestrata" / "workspace" / "private-app",
            source_url="https://github.com/org/private-app.git",
            files=[],
            metadata={
                "token_env": "CODESTRATA_GITHUB_TOKEN",
                "askpass": "/tmp/codestrata-git-auth-xyz/codestrata-askpass.sh",
            },
        ),
        findings=[
            _finding(
                rule_id="SEC001",
                title="Auth meta",
                severity=Severity.LOW,
                metadata={
                    "token_env": "CODESTRATA_GITHUB_TOKEN",
                    "GIT_ASKPASS": "/tmp/codestrata-askpass.sh",
                    "provider_name": "native",
                },
                evidence=[
                    Evidence(
                        file_path="README.md",
                        description="helper=/tmp/codestrata-git-auth-xyz/codestrata-askpass.sh",
                    )
                ],
            )
        ],
    )
    context = LLMAnalysisContextBuilder().build(result)
    payload = llm_context_to_json(context)
    assert "CODESTRATA_GITHUB_TOKEN" not in payload
    assert "codestrata-askpass" not in payload
    assert "codestrata-git-auth" not in payload
    assert ".codestrata/workspace" not in payload
    assert context.repository.source_type == "github"
    assert context.findings[0].metadata == {"provider_name": "native"}


def test_json_round_trip_validation(tmp_path: Path) -> None:
    context = LLMAnalysisContextBuilder().build(_complete_result(tmp_path))
    payload = llm_context_to_json(context)
    restored = llm_context_from_json(payload)
    assert restored == context


def test_domain_models_remain_unchanged(tmp_path: Path) -> None:
    result = _complete_result(tmp_path)
    before = result.model_dump(mode="json")
    LLMAnalysisContextBuilder().build(result)
    after = result.model_dump(mode="json")
    assert before == after
    assert result.findings[1].evidence[0].file_path == "."
