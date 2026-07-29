"""HTML report layout, overflow, escaping, and path-hardening tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.models import (
    AnalysisResult,
    BuildFacts,
    CicdFacts,
    DependencyFacts,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Priority,
    Recommendation,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
    TechnologyCategory,
)
from codestrata.models.cicd import CicdPipeline
from codestrata.models.enums import Effort, RecommendationCategory, Risk
from codestrata.models.scan_comparison import ComparisonSummary, FactChange, ScanComparison
from codestrata.reporters.html_file_reporter import HtmlFileReporter
from codestrata.reporters.html_rendering import COLLECTION_COLLAPSE_THRESHOLD
from codestrata.static_analysis.models import StaticAnalysisResult, StaticAnalysisStatus


def _plain(html: str) -> str:
    return html.replace("<wbr>", "")


def _hardening_fixture(tmp_path: Path) -> AnalysisResult:
    long_name = "a" * 110
    deep_path = "/".join(["src", "main", "java"] + ["pkg"] * 12 + ["DeepFile.java"])
    long_maven = (
        "com.example.enterprise.very.long.group:"
        "artifact-with-an-extremely-long-name-and-classifier:"
        "1.2.3-SNAPSHOT-with-extra-qualifiers"
    )
    assert len(long_maven) > 120

    framework_dependencies = [f"org.springframework:spring-core:{index}.0.0" for index in range(30)]
    plugins = [f"org.apache.maven.plugins:maven-plugin-{index}" for index in range(20)]
    actions = [f"actions/setup-java@{index}" for index in range(15)]

    absolute_repo = tmp_path / "workspace" / "clone"
    absolute_repo.mkdir(parents=True)

    return AnalysisResult(
        repository=Repository(
            name=long_name,
            path=absolute_repo,
            files=[deep_path, "pom.xml"],
        ),
        technologies=[
            Technology(
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="test",
            )
        ],
        facts=RepositoryFacts(
            build=BuildFacts(
                build_systems=["maven"],
                build_files=["pom.xml"],
                plugins=plugins,
                inferred_commands=["./mvnw -B verify"],
            ),
            dependencies=DependencyFacts(
                dependency_count=30,
                framework_dependencies=framework_dependencies,
                testing_libraries=["org.junit.jupiter:junit-jupiter"],
                database_drivers=["org.postgresql:postgresql"],
                cloud_sdks=["software.amazon.awssdk:s3"],
            ),
            cicd=CicdFacts(
                has_ci=True,
                ci_platforms=["github-actions"],
                pipeline_count=1,
                pipeline_files=[".github/workflows/ci.yml"],
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/ci.yml",
                        build_commands=["./mvnw -B package"],
                        test_commands=["./mvnw -B verify"],
                        metadata={"actions": actions},
                    )
                ],
            ),
        ),
        findings=[
            Finding(
                rule_id="PMD.JAVA.BESTPRACTICES." + ("UnusedPrivateField" * 4),
                title="Long PMD rule",
                description='Finding with HTML <script>alert("x")</script> & "quotes"',
                category=FindingCategory.RELIABILITY,
                severity=Severity.MEDIUM,
                source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
                evidence=[
                    Evidence(
                        file_path=deep_path,
                        line_number=42,
                        column_number=9,
                        description=(
                            "Very long evidence description that mentions "
                            "com.example.package.ClassName and path/segments " + ("detail-" * 40)
                        ),
                        detected_value="café & <tag>",
                    )
                ],
                affected_technologies=["Java"],
                metadata={
                    "provider_name": "PMD",
                    "provider_id": "pmd",
                    "ruleset": "category/java/bestpractices.xml",
                    "original_priority": 3,
                },
            ),
            Finding(
                rule_id="SEC003",
                title="Secret finding",
                description="Critical finding stays visible",
                category=FindingCategory.SECURITY,
                severity=Severity.CRITICAL,
                source=FindingSource.DETERMINISTIC,
                evidence=[
                    Evidence(file_path="config/application.yml"),
                ],
            ),
        ],
        recommendations=[
            Recommendation(
                rule_id="REC.SECURITY.001",
                title="Rotate credentials",
                description="Rotate",
                rationale="Security",
                priority=Priority.CRITICAL,
                category=RecommendationCategory.SECURITY,
                effort=Effort.MEDIUM,
                risk=Risk.HIGH,
                evidence=[
                    Evidence(
                        file_path="config/application.yml",
                        line_number=12,
                        description="Credential pattern",
                    )
                ],
                related_finding_ids=["SEC003"],
                actions=["Rotate secrets"],
            )
        ],
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="PMD",
                provider_version="7.1.0-long-build-metadata-string",
                status=StaticAnalysisStatus.COMPLETED,
                files_analyzed=12,
                duration_ms=123.4,
                warnings=[
                    "Long provider warning mentioning ruleset path "
                    "category/java/bestpractices.xml and version notes"
                ],
                command_metadata={
                    "executable": str(tmp_path / "bin" / "pmd"),
                    "temp_report": str(tmp_path / "codestrata-pmd-report.xml"),
                },
            )
        ],
        comparison=ScanComparison(
            baseline_available=True,
            baseline_timestamp="20260101-010101",
            current_timestamp="20260102-020202",
            baseline_analyzer_version="0.3.0-very-long-analyzer-version-string",
            current_analyzer_version="0.4.0-another-long-analyzer-version-string",
            baseline_ruleset_version="1.0.0-ruleset-with-long-identifier",
            current_ruleset_version="1.2.0-ruleset-with-long-identifier",
            summary=ComparisonSummary(fact_changes=1, new_findings=1),
            notes=["Provider versions changed: PMD 7.0.0 → 7.1.0"],
            fact_changes=[
                FactChange(
                    path="facts.cicd.pipelines",
                    change_type="changed",
                    summary=(
                        ".github/workflows/ci.yml: build capability No → Yes; "
                        "added path segments/and/commands ./mvnw -B package"
                    ),
                )
            ],
        ),
        analyzer_version="0.4.0-test",
        ruleset_version="1.2.0",
    )


def test_html_layout_structure_and_responsive_css(tmp_path: Path) -> None:
    html = HtmlFileReporter().render(_hardening_fixture(tmp_path))

    assert 'class="table-wrapper"' in html
    assert "fact-table" in html
    assert "expandable-collection" in html
    assert "value-list" in html
    assert "value-badges" in html
    assert "technical-value" in html
    assert "overflow-wrap: anywhere" in html
    assert "word-break: break-word" in html
    assert "min-width: 0" in html
    assert "@media (max-width: 768px)" in html
    assert "@media (max-width: 375px)" in html
    assert "@media print" in html
    assert "details > *" in html
    assert "details > summary" in html


def test_long_collections_collapse_with_correct_remaining_count(tmp_path: Path) -> None:
    html = HtmlFileReporter().render(_hardening_fixture(tmp_path))
    plain = _plain(html)

    assert "Show 22 more" in html  # 30 framework deps - threshold 8
    assert "Show 12 more" in html  # 20 plugins - threshold 8
    assert "Show 7 more" in html  # 15 actions - threshold 8
    assert "<details>" in html
    assert "<summary>" in html

    for index in range(30):
        assert f"org.springframework:spring-core:{index}.0.0" in plain
    for index in range(20):
        assert f"org.apache.maven.plugins:maven-plugin-{index}" in plain
    for index in range(15):
        assert f"actions/setup-java@{index}" in plain


def test_threshold_boundary_collections(tmp_path: Path) -> None:
    at_threshold = [f"item-{index}" for index in range(COLLECTION_COLLAPSE_THRESHOLD)]
    over_threshold = [f"item-{index}" for index in range(COLLECTION_COLLAPSE_THRESHOLD + 1)]

    at_html = HtmlFileReporter().render(
        AnalysisResult(
            repository=Repository(name="boundary", path=tmp_path, files=[]),
            facts=RepositoryFacts(
                dependencies=DependencyFacts(framework_dependencies=at_threshold),
            ),
        )
    )
    over_html = HtmlFileReporter().render(
        AnalysisResult(
            repository=Repository(name="boundary", path=tmp_path, files=[]),
            facts=RepositoryFacts(
                dependencies=DependencyFacts(framework_dependencies=over_threshold),
            ),
        )
    )

    assert "Show " not in at_html
    assert "Show 1 more" in over_html
    assert all(value in _plain(at_html) for value in at_threshold)
    assert all(value in _plain(over_html) for value in over_threshold)


def test_html_escaping_and_wrap_markers_are_safe(tmp_path: Path) -> None:
    html = HtmlFileReporter().render(_hardening_fixture(tmp_path))

    assert "<script>alert(" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "café" in html
    assert "<wbr>" in html


def test_evidence_locations_format_and_wrap(tmp_path: Path) -> None:
    html = HtmlFileReporter().render(_hardening_fixture(tmp_path))
    plain = _plain(html)

    deep_path = "/".join(["src", "main", "java"] + ["pkg"] * 12 + ["DeepFile.java"])
    assert f"{deep_path}:42:9" in plain
    assert "config/application.yml:12" in plain
    assert "evidence-location" in html
    assert "None:None" not in plain
    assert ":None" not in plain


def test_provider_and_comparison_content_stays_safe(tmp_path: Path) -> None:
    result = _hardening_fixture(tmp_path)
    html = HtmlFileReporter().render(result)
    plain = _plain(html)

    assert "Static Analysis Providers" in html
    assert "completed" in html
    assert "Long provider warning" in plain
    assert "Changes Since Previous Scan" in html
    assert "build capability No → Yes" in plain
    assert "{'path'" not in html
    assert "FactChange(" not in html
    assert str(result.repository.path) not in html
    assert str(tmp_path / "bin" / "pmd") not in html
    assert "codestrata-pmd-report.xml" not in html


def test_absolute_paths_are_not_exposed(tmp_path: Path) -> None:
    result = _hardening_fixture(tmp_path)
    html = HtmlFileReporter().render(result)
    home = str(Path.home())

    assert str(result.repository.path.resolve()) not in html
    assert str(tmp_path.resolve() / "bin" / "pmd") not in html
    assert home not in html
    assert "/var/folders" not in html
    assert "codestrata-pmd-" not in html
    assert ".codestrata/workspace/" not in html
