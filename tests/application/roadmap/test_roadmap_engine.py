"""Modernization Roadmap Engine tests (Phase 5.10)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.roadmap import ModernizationRoadmapEngine
from codestrata.application.roadmap.mapping import (
    RoadmapSourceEvidence,
    RoadmapSourceFinding,
    RoadmapSourceRecommendation,
    map_effort,
    map_phase,
    map_priority,
    map_risk,
)
from codestrata.config import load_settings
from codestrata.domain.roadmap.enums import (
    RoadmapEffort,
    RoadmapPhaseName,
    RoadmapPriority,
    RoadmapRisk,
    RoadmapStatus,
)
from codestrata.models import AnalysisResult, Repository, RepositoryFacts, StructureFacts
from codestrata.reporting.assessment_json import (
    ASSESSMENT_JSON_SCHEMA_VERSION,
    build_assessment_json_document,
)
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.roadmap.adapter import RoadmapReportAdapter


def _rec(
    *,
    rec_id: str,
    title: str,
    category: str,
    priority: str = "high",
    findings: tuple[str, ...] = (),
    actions: int = 2,
    effort: str | None = None,
    risk: str | None = None,
) -> RoadmapSourceRecommendation:
    return RoadmapSourceRecommendation(
        id=rec_id,
        title=title,
        summary=title,
        priority=priority,
        category=category,
        related_finding_ids=findings,
        evidence=(
            RoadmapSourceEvidence(
                evidence_type="recommendation",
                source_id=rec_id,
                path=f"path/{rec_id}.md",
            ),
        ),
        action_count=actions,
        effort=effort,
        risk=risk,
    )


def _finding(
    *,
    finding_id: str,
    category: str,
    severity: str = "medium",
) -> RoadmapSourceFinding:
    return RoadmapSourceFinding(
        id=finding_id,
        title=finding_id,
        severity=severity,
        category=category,
        evidence=(
            RoadmapSourceEvidence(
                evidence_type="finding",
                source_id=finding_id,
                path=f"src/{finding_id}.py",
            ),
        ),
    )


def test_mapping_rules() -> None:
    assert map_phase("testing") == RoadmapPhaseName.STABILIZE
    assert map_phase("security") == RoadmapPhaseName.SECURE
    assert map_phase("architecture") == RoadmapPhaseName.MODERNIZE
    assert map_phase("performance") == RoadmapPhaseName.OPTIMIZE
    assert map_phase("dependencies") == RoadmapPhaseName.MODERNIZE
    assert map_priority("immediate") == RoadmapPriority.CRITICAL
    assert map_effort("small", action_count=9) == RoadmapEffort.S
    assert map_effort(None, action_count=5) == RoadmapEffort.L
    assert map_risk("low", priority=RoadmapPriority.CRITICAL) == RoadmapRisk.HIGH
    assert (
        map_risk(None, priority=RoadmapPriority.LOW, finding_severities=("critical",))
        == RoadmapRisk.HIGH
    )


def test_deterministic_repeated_output() -> None:
    recommendations = (
        _rec(rec_id="rec-b", title="B", category="testing", findings=("f-1",)),
        _rec(
            rec_id="rec-a",
            title="A",
            category="security",
            findings=("f-2",),
            priority="critical",
        ),
        _rec(rec_id="rec-c", title="C", category="architecture", findings=("f-3",)),
    )
    findings = (
        _finding(finding_id="f-1", category="testing"),
        _finding(finding_id="f-2", category="security", severity="high"),
        _finding(finding_id="f-3", category="architecture"),
    )
    engine = ModernizationRoadmapEngine()
    first = engine.generate(recommendations=recommendations, findings=findings)
    second = engine.generate(
        recommendations=tuple(reversed(recommendations)),
        findings=tuple(reversed(findings)),
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert [item.initiative_id for item in first.initiatives] == [
        item.initiative_id for item in second.initiatives
    ]


def test_grouping_and_deduplication() -> None:
    recommendations = (
        _rec(rec_id="rec-1", title="Add tests", category="testing", findings=("f-1",)),
        _rec(rec_id="rec-1", title="Add tests duplicate", category="testing", findings=("f-1",)),
        _rec(rec_id="rec-2", title="Docs", category="documentation", findings=("f-2",)),
    )
    section = ModernizationRoadmapEngine().generate(recommendations=recommendations)
    stabilize = [item for item in section.initiatives if item.phase == RoadmapPhaseName.STABILIZE]
    assert len(stabilize) == 2
    testing = next(item for item in stabilize if item.category == "testing")
    assert testing.supporting_recommendation_ids == ("rec-1",)


def test_phase_assignment_and_dependency_ordering() -> None:
    recommendations = (
        _rec(rec_id="r-test", title="Tests", category="testing", findings=("f1",)),
        _rec(rec_id="r-sec", title="Secrets", category="security", findings=("f2",)),
        _rec(rec_id="r-arch", title="Boundaries", category="architecture", findings=("f3",)),
        _rec(rec_id="r-perf", title="Cache", category="performance", findings=("f4",)),
    )
    section = ModernizationRoadmapEngine().generate(recommendations=recommendations)
    phases = [item.phase for item in section.phases]
    assert phases == [
        RoadmapPhaseName.STABILIZE,
        RoadmapPhaseName.SECURE,
        RoadmapPhaseName.MODERNIZE,
        RoadmapPhaseName.OPTIMIZE,
    ]
    by_phase = {item.phase: item for item in section.initiatives}
    stabilize_id = by_phase[RoadmapPhaseName.STABILIZE].initiative_id
    secure = by_phase[RoadmapPhaseName.SECURE]
    modernize = by_phase[RoadmapPhaseName.MODERNIZE]
    optimize = by_phase[RoadmapPhaseName.OPTIMIZE]
    assert stabilize_id in secure.depends_on_initiative_ids
    assert stabilize_id in modernize.depends_on_initiative_ids
    assert secure.initiative_id in modernize.depends_on_initiative_ids
    assert modernize.initiative_id in optimize.depends_on_initiative_ids


def test_priority_effort_risk_mapping() -> None:
    recommendations = (
        _rec(
            rec_id="r1",
            title="Critical fix",
            category="security",
            priority="immediate",
            findings=("f1",),
            actions=8,
        ),
    )
    findings = (_finding(finding_id="f1", category="security", severity="critical"),)
    section = ModernizationRoadmapEngine().generate(
        recommendations=recommendations,
        findings=findings,
    )
    initiative = section.initiatives[0]
    assert initiative.priority == RoadmapPriority.CRITICAL
    assert initiative.effort == RoadmapEffort.XL
    assert initiative.risk == RoadmapRisk.HIGH


def test_traceability() -> None:
    recommendations = (
        _rec(rec_id="r1", title="Fix", category="dependency", findings=("f1", "f2")),
    )
    findings = (
        _finding(finding_id="f1", category="dependency"),
        _finding(finding_id="f2", category="dependency"),
    )
    section = ModernizationRoadmapEngine().generate(
        recommendations=recommendations,
        findings=findings,
    )
    initiative = section.initiatives[0]
    assert initiative.supporting_recommendation_ids == ("r1",)
    assert initiative.supporting_finding_ids == ("f1", "f2")
    assert initiative.evidence_references
    assert all(item.startswith("roadmap-initiative:") for item in [initiative.initiative_id])


def test_empty_and_sparse_input() -> None:
    empty = ModernizationRoadmapEngine().generate()
    assert empty.status == RoadmapStatus.EMPTY
    assert empty.initiatives == ()
    assert empty.assumptions
    assert empty.limitations

    sparse = ModernizationRoadmapEngine().generate(
        findings=(_finding(finding_id="only", category="testing"),)
    )
    assert sparse.status == RoadmapStatus.EMPTY
    assert "no recommendations" in " ".join(sparse.limitations).lower()


def test_configuration_disabled_by_default(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.report.sections.roadmap.enabled is False
    assert settings.report.sections.roadmap.include_assumptions is True


def test_roadmap_can_be_enabled(tmp_path: Path) -> None:
    config_file = tmp_path / "codestrata.toml"
    config_file.write_text(
        """
        [repository]
        path = "."

        [report.sections.roadmap]
        enabled = true
        include_evidence = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config_file)
    assert settings.report.sections.roadmap.enabled is True
    assert settings.report.sections.roadmap.include_evidence is False


def _analysis_result(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "workspace" / "sample-app",
            source_url="https://github.com/example/sample-app.git",
            default_branch="main",
            files=["src/App.java"],
            total_files=1,
        ),
        technologies=[],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=1,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[],
        recommendations=[],
    )


def test_json_serialization_html_and_schema_compatibility(tmp_path: Path) -> None:
    recommendations = (
        _rec(rec_id="r-test", title="Tests", category="testing", findings=("f1",)),
        _rec(rec_id="r-sec", title="Secrets", category="security", findings=("f2",)),
    )
    domain = ModernizationRoadmapEngine().generate(recommendations=recommendations)
    report = RoadmapReportAdapter().adapt(domain)
    payload = report.model_dump(mode="json")
    assert payload["section_id"] == "report.roadmap"
    assert payload["status"] == "succeeded"
    assert len(payload["phases"]) == 2

    analysis = _analysis_result(tmp_path)
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
        roadmap_report=report,
    )
    document = build_assessment_json_document(report_input)
    assert document["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    assert document["schema_version"] == "1.2"
    assert "roadmap" in document["assessment"]
    assert document["assessment"]["roadmap"]["initiatives_total"] == 2

    without = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
    )
    baseline = build_assessment_json_document(without)
    assert "roadmap" not in baseline["assessment"]
    assert baseline["schema_version"] == "1.2"

    view = build_html_report_view_model(report_input)
    html = HtmlReportRenderer().render(view)
    assert 'id="phased-modernization-plan"' in html
    assert (
        "Implementation Sequence" in html
        or "Phased Modernization Plan" in html
        or "Roadmap" in html
    )
    assert "Stabilize" in html
    assert "Secure" in html


def test_adapter_disabled_evidence() -> None:
    domain = ModernizationRoadmapEngine().generate(
        recommendations=(_rec(rec_id="r1", title="T", category="testing", findings=("f1",)),)
    )
    report = RoadmapReportAdapter().adapt(domain, include_evidence=False)
    assert all(not item.evidence_references for item in report.initiatives)
