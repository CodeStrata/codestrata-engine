"""Cloud synthesis tests (Phase 4.7.5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.application.cloud.assessment.artifacts import (
    cloud_assessment_payload as build_cloud_assessment_payload,
)
from codestrata.application.cloud.assessment.artifacts import (
    write_cloud_assessment_artifact,
)
from codestrata.application.cloud.assessment.assembler import CloudAssessmentAssembler
from codestrata.application.cloud.assessment.inventory import execution_facts_from_status_map
from codestrata.application.cloud.synthesis import synthesize_cloud
from codestrata.config import load_settings
from codestrata.domain.cloud.assessment.enums import (
    CloudAssessmentStatus,
    CloudLimitationCategory,
)
from codestrata.domain.cloud.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.cloud.assessment.models import (
    CloudFindingInventory,
    CloudLimitation,
    CloudRuleInventory,
    CloudTechnologyFamilyInventory,
)
from codestrata.domain.cloud.ids import (
    HYGIENE_RULE_IDS,
    RULE_CLOUD_NATIVE_INDICATORS,
    RULE_CONTAINERIZATION,
    RULE_DEPLOYMENT_PIPELINE,
    RULE_DEPLOYMENT_WITHOUT_PLATFORM,
    RULE_IAC_PRESENT,
    RULE_KUBERNETES,
    RULE_MANAGED_SERVICES,
    RULE_MULTIPLE_IAC,
    RULE_MULTIPLE_PLATFORMS,
    RULE_PLATFORM_DETECTED,
    RULE_SERVERLESS,
)
from codestrata.domain.cloud.synthesis.enums import (
    CloudConclusionKind,
    CloudRecommendationKind,
    CloudSynthesisStatus,
    CloudThemeKind,
)
from codestrata.domain.cloud.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.services.artifact_serialization import dumps_stable_json


def _finding(
    *,
    rule_id: str,
    finding_id: str,
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
    confidence: str = "high",
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=severity,
        category=FindingCategory.CLOUD,
        metadata={"confidence": confidence},
    )


def _facts_all_matched(matched: set[str]) -> tuple:
    status = {
        rule_id: ("matched" if rule_id in matched else "not_matched")
        for rule_id in HYGIENE_RULE_IDS
    }
    return execution_facts_from_status_map(status)


def _limitation() -> CloudLimitation:
    return CloudLimitation(
        limitation_id="cloud-limitation:provider-apis",
        category=CloudLimitationCategory.PROVIDER_DETECTION_NOT_IMPLEMENTED,
        summary="Cloud provider APIs are out of scope for this assessment.",
        affected_capability="cloud",
    )


def _rule_inventory(*, matched: int, executed: int | None = None) -> CloudRuleInventory:
    executed_count = executed if executed is not None else len(HYGIENE_RULE_IDS)
    return CloudRuleInventory(
        rules_planned=len(HYGIENE_RULE_IDS),
        rules_executed=executed_count,
        rules_matched=matched,
        rules_not_matched=max(executed_count - matched, 0),
    )


def test_schema_and_synthesis_gate(tmp_path: Path) -> None:
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert SYNTHESIS_VERSION == "1.0.0"
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [rules]
        enabled = true
        [rules.cloud]
        enabled = true
        [analysis.cloud]
        enabled = true
        include_synthesis = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.analysis.cloud.include_synthesis is False
    section = CloudAssessmentAssembler().assemble(
        repository_id="repo:gate",
        findings=(),
        include_synthesis=False,
        rules_executed=len(HYGIENE_RULE_IDS),
        rule_execution_facts=_facts_all_matched(set()),
        evidence_fingerprint="syn-fp-1",
    )
    assert section.section_version == "1.2.0"
    assert section.synthesis.status is CloudSynthesisStatus.NOT_REQUESTED
    assert section.metadata.get("assessment_milestone") == "4.7.5"
    assert section.metadata.get("synthesis_version") == SYNTHESIS_VERSION


def test_zero_findings_neutral_posture() -> None:
    result = synthesize_cloud(
        repository_id="repo:empty",
        pack_enabled=True,
        section_status=CloudAssessmentStatus.SUCCEEDED,
        findings=(),
        finding_inventory=CloudFindingInventory(),
        rule_inventory=_rule_inventory(matched=0),
        evidence_status="succeeded",
    )
    assert result.status is CloudSynthesisStatus.EMPTY
    kinds = {item.kind for item in result.themes}
    assert CloudThemeKind.CLOUD_HYGIENE_LANDSCAPE in kinds
    assert CloudThemeKind.RULE_EXECUTION_COVERAGE in kinds
    assert CloudThemeKind.NO_HYGIENE_FINDINGS in kinds
    assert CloudThemeKind.CLOUD_PLATFORM_ADOPTION not in kinds
    assert result.overall_posture_summary
    joined = " ".join(
        [
            result.overall_posture_summary,
            *(item.summary for item in result.conclusions),
            *(item.action for item in result.recommendations),
        ]
    ).lower()
    assert "cloud ready" not in joined or "does not" in joined
    assert "migrate to" not in joined
    assert "modernize" not in joined
    assert "no cloud issues" not in joined


def test_each_supported_theme() -> None:
    cases = [
        (
            RULE_PLATFORM_DETECTED,
            CloudThemeKind.CLOUD_PLATFORM_ADOPTION,
            CloudConclusionKind.CLOUD_PLATFORM_ADOPTION_OBSERVED,
            CloudRecommendationKind.REVIEW_CLOUD_PLATFORM_SIGNALS,
        ),
        (
            RULE_MULTIPLE_PLATFORMS,
            CloudThemeKind.MULTI_CLOUD_PRESENCE,
            CloudConclusionKind.MULTI_CLOUD_PRESENCE_OBSERVED,
            CloudRecommendationKind.REVIEW_MULTI_CLOUD_SIGNALS,
        ),
        (
            RULE_CONTAINERIZATION,
            CloudThemeKind.CONTAINERIZATION_MATURITY,
            CloudConclusionKind.CONTAINERIZATION_OBSERVED,
            CloudRecommendationKind.REVIEW_CONTAINERIZATION_SIGNALS,
        ),
        (
            RULE_KUBERNETES,
            CloudThemeKind.KUBERNETES_ORCHESTRATION_ADOPTION,
            CloudConclusionKind.KUBERNETES_ORCHESTRATION_OBSERVED,
            CloudRecommendationKind.REVIEW_ORCHESTRATION_SIGNALS,
        ),
        (
            RULE_IAC_PRESENT,
            CloudThemeKind.IAC_MATURITY,
            CloudConclusionKind.IAC_MATURITY_OBSERVED,
            CloudRecommendationKind.REVIEW_IAC_SIGNALS,
        ),
        (
            RULE_MULTIPLE_IAC,
            CloudThemeKind.IAC_MATURITY,
            CloudConclusionKind.IAC_MATURITY_OBSERVED,
            CloudRecommendationKind.REVIEW_IAC_SIGNALS,
        ),
        (
            RULE_SERVERLESS,
            CloudThemeKind.SERVERLESS_ADOPTION,
            CloudConclusionKind.SERVERLESS_ADOPTION_OBSERVED,
            CloudRecommendationKind.REVIEW_SERVERLESS_SIGNALS,
        ),
        (
            RULE_MANAGED_SERVICES,
            CloudThemeKind.MANAGED_CLOUD_SERVICE_USAGE,
            CloudConclusionKind.MANAGED_CLOUD_SERVICES_OBSERVED,
            CloudRecommendationKind.REVIEW_MANAGED_SERVICE_SIGNALS,
        ),
        (
            RULE_DEPLOYMENT_PIPELINE,
            CloudThemeKind.CLOUD_DEPLOYMENT_AUTOMATION,
            CloudConclusionKind.CLOUD_DEPLOYMENT_AUTOMATION_OBSERVED,
            CloudRecommendationKind.REVIEW_DEPLOYMENT_PIPELINE_SIGNALS,
        ),
        (
            RULE_CLOUD_NATIVE_INDICATORS,
            CloudThemeKind.CLOUD_TECHNOLOGY_COVERAGE,
            CloudConclusionKind.CLOUD_TECHNOLOGY_COVERAGE_OBSERVED,
            CloudRecommendationKind.REVIEW_CLOUD_TECHNOLOGY_COVERAGE,
        ),
        (
            RULE_DEPLOYMENT_WITHOUT_PLATFORM,
            CloudThemeKind.DEPLOYMENT_WITHOUT_PLATFORM,
            CloudConclusionKind.DEPLOYMENT_WITHOUT_PLATFORM_OBSERVED,
            CloudRecommendationKind.REVIEW_DEPLOYMENT_WITHOUT_PLATFORM,
        ),
    ]
    for rule_id, theme_kind, conclusion_kind, recommendation_kind in cases:
        finding = _finding(rule_id=rule_id, finding_id=f"f-{rule_id}")
        result = synthesize_cloud(
            repository_id="repo:themes",
            pack_enabled=True,
            section_status=CloudAssessmentStatus.SUCCEEDED,
            findings=(finding,),
            finding_inventory=CloudFindingInventory(
                finding_ids=(finding.id,),
                finding_count=1,
                rule_counts={rule_id: 1},
            ),
            rule_inventory=_rule_inventory(matched=1),
        )
        assert result.status is CloudSynthesisStatus.SUCCEEDED
        assert theme_kind in {item.kind for item in result.themes}
        assert conclusion_kind in {item.kind for item in result.conclusions}
        assert recommendation_kind in {item.kind for item in result.recommendations}
        rec = next(item for item in result.recommendations if item.kind is recommendation_kind)
        assert finding.id in rec.finding_ids
        assert rule_id in rec.rule_ids
        assert rec.conclusion_ids


def test_technology_coverage_from_families_without_cloud060() -> None:
    findings = (
        _finding(rule_id=RULE_CONTAINERIZATION, finding_id="f-ctr"),
        _finding(rule_id=RULE_KUBERNETES, finding_id="f-k8s"),
        _finding(rule_id=RULE_DEPLOYMENT_PIPELINE, finding_id="f-dep"),
    )
    result = synthesize_cloud(
        repository_id="repo:partial",
        pack_enabled=True,
        section_status=CloudAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=CloudFindingInventory(
            finding_ids=("f-ctr", "f-dep", "f-k8s"),
            finding_count=3,
        ),
        rule_inventory=_rule_inventory(matched=3),
        technology_family_inventory=CloudTechnologyFamilyInventory(
            families_observed=3,
            families_total=7,
        ),
    )
    kinds = {item.kind for item in result.themes}
    assert CloudThemeKind.CONTAINERIZATION_MATURITY in kinds
    assert CloudThemeKind.KUBERNETES_ORCHESTRATION_ADOPTION in kinds
    assert CloudThemeKind.CLOUD_DEPLOYMENT_AUTOMATION in kinds
    assert CloudThemeKind.CLOUD_TECHNOLOGY_COVERAGE in kinds
    assert CloudThemeKind.CLOUD_PLATFORM_ADOPTION not in kinds
    assert CloudThemeKind.SERVERLESS_ADOPTION not in kinds


def test_unsupported_scope_theme() -> None:
    result = synthesize_cloud(
        repository_id="repo:limits",
        pack_enabled=True,
        section_status=CloudAssessmentStatus.SUCCEEDED,
        findings=(),
        finding_inventory=CloudFindingInventory(),
        rule_inventory=_rule_inventory(matched=0),
        limitations=(_limitation(),),
    )
    kinds = {item.kind for item in result.themes}
    assert CloudThemeKind.UNSUPPORTED_ANALYSIS_SCOPE in kinds
    assert CloudThemeKind.NO_HYGIENE_FINDINGS in kinds
    assert CloudRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_CLOUD_ANALYSIS_SCOPE in {
        item.kind for item in result.recommendations
    }


def test_partial_adoption_assembler(tmp_path: Path) -> None:
    findings = (
        _finding(rule_id=RULE_CONTAINERIZATION, finding_id="f-001"),
        _finding(
            rule_id=RULE_KUBERNETES,
            finding_id="f-002",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    section = CloudAssessmentAssembler().assemble(
        repository_id="repo:partial",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        rule_execution_facts=_facts_all_matched({RULE_CONTAINERIZATION, RULE_KUBERNETES}),
        evidence_fingerprint="syn-fp-1",
        configuration_payload="partial-config",
    )
    assert section.synthesis.status is CloudSynthesisStatus.SUCCEEDED
    theme_kinds = {item.kind for item in section.themes}
    assert CloudThemeKind.CONTAINERIZATION_MATURITY in theme_kinds
    assert CloudThemeKind.KUBERNETES_ORCHESTRATION_ADOPTION in theme_kinds
    assert CloudThemeKind.UNSUPPORTED_ANALYSIS_SCOPE in theme_kinds
    assert CloudThemeKind.SERVERLESS_ADOPTION not in theme_kinds
    assert CloudThemeKind.IAC_MATURITY not in theme_kinds
    assert section.execution_summary.theme_count == len(section.themes)
    assert section.execution_summary.conclusion_count == len(section.conclusions)
    assert section.execution_summary.recommendation_count == len(section.recommendations)
    for recommendation in section.recommendations:
        assert recommendation.conclusion_ids
        if recommendation.kind in {
            CloudRecommendationKind.REVIEW_CONTAINERIZATION_SIGNALS,
            CloudRecommendationKind.REVIEW_ORCHESTRATION_SIGNALS,
        }:
            assert recommendation.finding_ids
            assert recommendation.rule_ids
    body = dumps_stable_json(build_cloud_assessment_payload(section))
    assert '"themes"' in body
    assert '"conclusions"' in body
    assert '"recommendations"' in body
    assert '"overall_posture_summary"' in body
    write_cloud_assessment_artifact(section, tmp_path)
    assert (tmp_path / "cloud-assessment.json").read_text(encoding="utf-8") == body


def test_cloud_native_broad_adoption() -> None:
    findings = (
        _finding(rule_id=RULE_PLATFORM_DETECTED, finding_id="f-plat"),
        _finding(rule_id=RULE_CONTAINERIZATION, finding_id="f-ctr"),
        _finding(rule_id=RULE_KUBERNETES, finding_id="f-k8s"),
        _finding(rule_id=RULE_IAC_PRESENT, finding_id="f-iac"),
        _finding(rule_id=RULE_SERVERLESS, finding_id="f-sls"),
        _finding(rule_id=RULE_MANAGED_SERVICES, finding_id="f-mgt"),
        _finding(rule_id=RULE_DEPLOYMENT_PIPELINE, finding_id="f-dep"),
        _finding(rule_id=RULE_CLOUD_NATIVE_INDICATORS, finding_id="f-nat"),
    )
    result = synthesize_cloud(
        repository_id="repo:cloud-native",
        pack_enabled=True,
        section_status=CloudAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=CloudFindingInventory(
            finding_ids=tuple(item.id for item in findings),
            finding_count=8,
        ),
        rule_inventory=_rule_inventory(matched=8),
        technology_family_inventory=CloudTechnologyFamilyInventory(
            families_observed=7,
            families_total=7,
        ),
        limitations=(_limitation(),),
    )
    assert result.status is CloudSynthesisStatus.SUCCEEDED
    kinds = {item.kind for item in result.themes}
    for expected in (
        CloudThemeKind.CLOUD_PLATFORM_ADOPTION,
        CloudThemeKind.CONTAINERIZATION_MATURITY,
        CloudThemeKind.KUBERNETES_ORCHESTRATION_ADOPTION,
        CloudThemeKind.IAC_MATURITY,
        CloudThemeKind.SERVERLESS_ADOPTION,
        CloudThemeKind.MANAGED_CLOUD_SERVICE_USAGE,
        CloudThemeKind.CLOUD_DEPLOYMENT_AUTOMATION,
        CloudThemeKind.CLOUD_TECHNOLOGY_COVERAGE,
        CloudThemeKind.UNSUPPORTED_ANALYSIS_SCOPE,
    ):
        assert expected in kinds
    assert CloudThemeKind.NO_HYGIENE_FINDINGS not in kinds


def test_deterministic_ordering_and_ids() -> None:
    findings = (
        _finding(rule_id=RULE_KUBERNETES, finding_id="f-b"),
        _finding(rule_id=RULE_CONTAINERIZATION, finding_id="f-a"),
    )
    left = synthesize_cloud(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=CloudAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=CloudFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=_rule_inventory(matched=2),
    )
    right = synthesize_cloud(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=CloudAssessmentStatus.SUCCEEDED,
        findings=tuple(reversed(findings)),
        finding_inventory=CloudFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=_rule_inventory(matched=2),
    )
    assert left.model_dump_json() == right.model_dump_json()
    assert left.theme_ids == tuple(item.theme_id for item in left.themes)
    assert left.conclusion_ids == tuple(item.conclusion_id for item in left.conclusions)
    assert all(item.startswith("cloud-theme:") for item in left.theme_ids)
    assert all(item.startswith("cloud-conclusion:") for item in left.conclusion_ids)
    assert all(item.startswith("cloud-recommendation:") for item in left.recommendation_ids)


def test_disabled_and_insufficient_synthesis() -> None:
    disabled = synthesize_cloud(
        repository_id="repo:x",
        pack_enabled=False,
        section_status=CloudAssessmentStatus.DISABLED,
    )
    assert disabled.status is CloudSynthesisStatus.DISABLED
    insufficient = synthesize_cloud(
        repository_id="repo:x",
        pack_enabled=True,
        section_status=CloudAssessmentStatus.INSUFFICIENT_EVIDENCE,
    )
    assert insufficient.status is CloudSynthesisStatus.INSUFFICIENT_EVIDENCE


def test_synthesis_failure_isolation() -> None:
    with patch(
        "codestrata.application.cloud.assessment.assembler.synthesize_cloud",
        side_effect=RuntimeError("boom"),
    ):
        section = CloudAssessmentAssembler().assemble(
            repository_id="repo:fail",
            findings=(),
            rules_executed=len(HYGIENE_RULE_IDS),
            rule_execution_facts=_facts_all_matched(set()),
            evidence_fingerprint="syn-fp-1",
        )
    assert section.synthesis.status is CloudSynthesisStatus.FAILED
    assert section.finding_inventory.finding_count == 0
    assert any("synthesis_failed" in item for item in section.diagnostics)
