"""Epic 3 Slice 3.7 — Cloud Readiness Intelligence section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.cloud.assessment.assembler import CloudAssessmentAssembler
from codestrata.application.cloud.assessment.inventory import execution_facts_from_status_map
from codestrata.domain.cloud.ids import (
    HYGIENE_RULE_IDS,
    RULE_CONTAINERIZATION,
    RULE_KUBERNETES,
    RULE_PLATFORM_DETECTED,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding, FindingEvidence
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.cloud import (
    CloudReportAdapter,
    build_cloud_intelligence,
)
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.models import EvidenceRefView, FindingView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput

_FORBIDDEN_CLAIMS = (
    "cloud ready",
    "migration ready",
    "cloud native",
    "cloud-native",
    "production ready",
    "highly available",
    "runs on aws",
    "runs on azure",
    "runs on gcp",
    "is cloud ready",
    "are cloud ready",
    "no cloud risks",
    "fully portable",
    "deployed to",
    "migrate to",
    "cost optimized",
    "secure cloud",
    "operationally mature",
)


def _facts(matched: set[str]):
    return execution_facts_from_status_map(
        {
            rule_id: ("matched" if rule_id in matched else "not_matched")
            for rule_id in HYGIENE_RULE_IDS
        }
    )


def _finding(
    *,
    rule_id: str,
    path: str,
    finding_id: str,
    metadata: dict[str, str] | None = None,
) -> Finding:
    base = {
        "confidence": "high",
        "path": path,
        "evidence_id": f"ev:{path}",
    }
    if metadata:
        base.update(metadata)
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} at {path}",
        description=f"Bounded explanation for {path}",
        severity=FindingSeverity.INFORMATIONAL,
        category=FindingCategory.CLOUD,
        evidence=(
            FindingEvidence(
                evidence_type="repository_cloud",
                source_id=f"ev:{path}",
                path=path,
                excerpt="Dockerfile",
            ),
        ),
        metadata=base,
    )


def _assemble(*, findings=()):
    matched = {item.rule_id for item in findings}
    return CloudAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=len(matched),
        rules_not_matched=len(HYGIENE_RULE_IDS) - len(matched),
        rule_execution_facts=_facts(matched),
        evidence_fingerprint="cloud-intel-fp",
        configuration_payload="cloud-intel",
    )


def _succeeded_report():
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_PLATFORM_DETECTED,
                path="deploy/aws.yaml",
                finding_id="plat",
                metadata={"platforms": "aws"},
            ),
            _finding(
                rule_id=RULE_CONTAINERIZATION,
                path="Dockerfile",
                finding_id="ctr",
                metadata={"container_kinds": "docker"},
            ),
            _finding(
                rule_id=RULE_KUBERNETES,
                path="k8s/deployment.yaml",
                finding_id="k8s",
                metadata={"orchestration_kinds": "kubernetes"},
            ),
        )
    )
    return CloudReportAdapter().adapt(assessment)


def _assert_no_forbidden(text: str) -> None:
    lowered = text.lower()
    sanitized = (
        lowered.replace("does not establish cloud readiness", "")
        .replace("cloud readiness", "")
        .replace("not cloud ready", "")
        .replace("do not establish cloud readiness", "")
        .replace("absence of findings does not establish cloud readiness", "")
    )
    for phrase in _FORBIDDEN_CLAIMS:
        assert phrase not in sanitized, f"forbidden claim present: {phrase}"


def test_build_cloud_intelligence_groups_and_excludes_others() -> None:
    report = _succeeded_report()
    plat = FindingView(
        finding_id="f-plat",
        rule_id=RULE_PLATFORM_DETECTED,
        title="Platform signal",
        description="platform observed",
        severity="informational",
        category="cloud",
        affected_nodes=("deploy/aws.yaml",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:deploy/aws.yaml",
                kind="other",
                path="deploy/aws.yaml",
                snippet_text="provider: aws",
            ),
        ),
    )
    ctr = FindingView(
        finding_id="f-ctr",
        rule_id=RULE_CONTAINERIZATION,
        title="Container signal",
        description="container observed",
        severity="informational",
        category="cloud",
        affected_nodes=("Dockerfile",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:Dockerfile",
                kind="other",
                path="Dockerfile",
                snippet_text="FROM alpine",
            ),
        ),
    )
    security = FindingView(
        finding_id="f-sec",
        rule_id="security.private-key-material",
        title="Private key",
        description="sec",
        severity="high",
        category="security",
    )
    dependency = FindingView(
        finding_id="f-dep",
        rule_id="dependency.unresolved-version",
        title="Unresolved",
        description="dep",
        severity="medium",
        category="dependency",
    )
    architecture = FindingView(
        finding_id="f-arch",
        rule_id="architecture.dependency-cycle",
        title="Cycle",
        description="cycle",
        severity="medium",
        category="architecture",
    )
    rec = RecommendationView(
        recommendation_id="r-cloud",
        title="Review container signals",
        summary="Review observed container declarations",
        rationale="Cloud",
        priority="medium",
        category="cloud",
        related_finding_ids=("f-ctr",),
    )
    other = RecommendationView(
        recommendation_id="r-dep",
        title="Pin versions",
        summary="Pin",
        rationale="Dependency",
        priority="high",
        category="dependency",
        related_finding_ids=("f-dep",),
    )
    intel = build_cloud_intelligence(
        report,
        findings=(plat, ctr, security, dependency, architecture),
        recommendations=(rec, other),
    )
    assert intel is not None
    assert {item.finding_id for item in intel.findings} == {"f-plat", "f-ctr"}
    assert {item.recommendation_id for item in intel.recommendations} == {"r-cloud"}
    assert intel.empty_findings_message is None
    assert intel.signal_groups
    group_ids = {group.group_id for group in intel.signal_groups}
    assert "containers" in group_ids or "platforms" in group_ids or "orchestration" in group_ids
    for group in intel.signal_groups:
        assert group.signals
        assert group.title
        for signal in group.signals:
            assert "were detected" in signal.label.lower()
            assert signal.path is None or not signal.path.startswith("/")
    joined = " ".join(intel.limitations).lower()
    assert "repository evidence only" in joined
    assert "no cloud-provider api" in joined
    assert "no live infrastructure" in joined
    assert "no numeric cloud-readiness score" in joined
    assert "do not prove successful deployment" in joined
    assert intel.confidence_label in {
        "High confidence",
        "Moderate confidence",
        "Limited confidence",
        "Confidence unavailable",
    }
    _assert_no_forbidden(
        " ".join(
            [
                intel.status_summary,
                *(f"{f.label} {f.value} {f.note or ''}" for f in intel.overview_facts),
                *intel.limitations,
                *(s.label for g in intel.signal_groups for s in g.signals),
                *(s.note or "" for g in intel.signal_groups for s in g.signals),
            ]
        )
    )


def test_zero_findings_not_cloud_ready() -> None:
    assessment = _assemble(findings=())
    report = CloudReportAdapter().adapt(assessment)
    intel = build_cloud_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.finding_count == 0
    assert intel.findings == ()
    assert intel.empty_findings_message is not None
    lowered = intel.empty_findings_message.lower()
    assert "absence of findings" in lowered
    assert "does not establish cloud readiness" in lowered
    _assert_no_forbidden(intel.empty_findings_message)
    overview = " ".join(
        f"{fact.label} {fact.value} {fact.note or ''}" for fact in intel.overview_facts
    ).lower()
    assert "zero findings do not establish cloud readiness" in overview


def test_soft_claims_scrubbed_from_status_summary() -> None:
    report = _succeeded_report()
    mutated = report.model_copy(
        update={
            "status_summary": (
                "Cloud ready and migration ready with highly available "
                "production ready posture that runs on AWS."
            ),
            "overall_posture_summary": (
                "Secure cloud operationally mature system with no cloud risks."
            ),
        }
    )
    intel = build_cloud_intelligence(mutated, findings=(), recommendations=())
    assert intel is not None
    lowered = intel.status_summary.lower()
    assert "cloud ready" not in lowered
    assert "migration ready" not in lowered
    assert "highly available" not in lowered
    assert "runs on aws" not in lowered
    assert "repository-observable" in lowered or "repository" in lowered
    joined_limits = " ".join(intel.limitations).lower()
    assert "live deployment posture" in joined_limits or "repository" in joined_limits
    _assert_no_forbidden(intel.status_summary)


def test_absolute_paths_omitted() -> None:
    report = _succeeded_report()
    ctr = FindingView(
        finding_id="f-ctr",
        rule_id=RULE_CONTAINERIZATION,
        title="Container signal",
        description="container",
        severity="informational",
        category="cloud",
        affected_nodes=("/Users/secret/Dockerfile",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:bad",
                kind="other",
                path="/Users/secret/Dockerfile",
                snippet_text="FROM alpine",
            ),
        ),
    )
    intel = build_cloud_intelligence(report, findings=(ctr,), recommendations=())
    assert intel is not None
    rendered_paths = " ".join(
        filter(
            None,
            [
                *(row.path for group in intel.signal_groups for row in group.signals),
                *(row.path for row in intel.findings),
            ],
        )
    )
    assert "/Users/secret" not in rendered_paths
    assert all(not (row.path or "").startswith("/") for row in intel.findings)
    assert all(not (row.path or "").startswith("file:") for row in intel.findings)


def test_html_cloud_intelligence_section(tmp_path: Path) -> None:
    report = _succeeded_report()
    analysis = AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["Dockerfile"],
            total_files=1,
        ),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        cloud_report=report,
    )
    document = build_html_report_view_model(report_input)
    assert document.cloud_intelligence is not None
    html = HtmlReportRenderer().render(document)
    assert 'id="cloud-readiness"' in html
    assert 'id="cloud-assessment"' in html
    assert 'href="#cloud-readiness"' in html
    assert "Cloud overview" in html
    assert "Limitations" in html
    assert "Confidence" in html
    assert "Repository evidence only" in html or "repository evidence only" in html.lower()
    lowered = html.lower()
    _assert_no_forbidden(lowered)
    assert "cloud ready" not in lowered
    assert "migration ready" not in lowered
    assert "highly available" not in lowered
    assert "runs on aws" not in lowered
    assert "/Users/" not in html
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    for anchor in (
        "technology-inventory",
        "architecture-intelligence",
        "technical-debt-intelligence",
        "dependency-intelligence",
        "security-intelligence",
        "cloud-readiness",
    ):
        assert f'id="{anchor}"' in html
        assert f'href="#{anchor}"' in html


def test_build_returns_none_when_report_missing() -> None:
    assert build_cloud_intelligence(None) is None


def test_related_recommendation_subset_included() -> None:
    report = _succeeded_report()
    cloud = FindingView(
        finding_id="f-cloud",
        rule_id=RULE_CONTAINERIZATION,
        title="Container",
        description="x",
        severity="informational",
        category="cloud",
    )
    related = RecommendationView(
        recommendation_id="r-related",
        title="Review container",
        summary="Review",
        rationale="Cloud",
        priority="medium",
        category="maintainability",
        related_finding_ids=("f-cloud",),
    )
    mixed = RecommendationView(
        recommendation_id="r-mixed",
        title="Mixed",
        summary="Mixed",
        rationale="Mixed",
        priority="medium",
        category="maintainability",
        related_finding_ids=("f-cloud", "f-other"),
    )
    intel = build_cloud_intelligence(
        report,
        findings=(cloud,),
        recommendations=(related, mixed),
    )
    assert intel is not None
    assert {item.recommendation_id for item in intel.recommendations} == {"r-related"}


def test_signal_groups_omit_empty_and_use_observational_labels() -> None:
    report = _succeeded_report()
    intel = build_cloud_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.signal_groups
    for group in intel.signal_groups:
        assert group.signals
        assert group.group_id in {
            "platforms",
            "containers",
            "orchestration",
            "iac",
            "serverless",
            "managed_services",
            "deployment_pipelines",
            "other",
        }
        for signal in group.signals:
            assert signal.label.lower().startswith("repository signals associated with")
            assert "were detected" in signal.label.lower()
            if signal.note:
                assert "do not" in signal.note.lower() or "does not" in signal.note.lower()
