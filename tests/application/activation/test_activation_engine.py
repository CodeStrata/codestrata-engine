"""Unit tests for Phase 7.1.1 smart default assessment activation."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.activation import (
    AssessmentActivationMode,
    PackId,
    apply_activation_plan,
    build_activation_plan,
    collect_explicit_activation_overrides,
    collect_repository_evidence,
    load_raw_toml_dict,
)
from codestrata.config import load_settings
from codestrata.models import AnalysisResult, Repository, Technology
from codestrata.models.dependency_facts import DependencyFacts, DependencyManifest
from codestrata.models.enums import TechnologyCategory
from codestrata.models.normalized_facts import (
    CloudReadinessFacts,
    StructureFacts,
    TechnologyFacts,
)
from codestrata.models.repository_facts import RepositoryFacts


def _analysis(
    *,
    name: str,
    files: list[str],
    languages: list[str] | None = None,
    frameworks: list[str] | None = None,
    has_tests: bool = False,
    test_file_count: int = 0,
    source_file_count: int = 0,
    layers: list[str] | None = None,
    manifests: list[DependencyManifest] | None = None,
    cloud: CloudReadinessFacts | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name=name,
            path=Path(f"/tmp/{name}"),
            files=files,
            total_files=len(files),
        ),
        technologies=[
            Technology(name=lang, category=TechnologyCategory.LANGUAGE)
            for lang in (languages or [])
        ],
        facts=RepositoryFacts(
            technology=TechnologyFacts(
                programming_languages=list(languages or []),
                frameworks=list(frameworks or []),
                detected_technologies=list(languages or []) + list(frameworks or []),
            ),
            structure=StructureFacts(
                has_tests=has_tests,
                test_file_count=test_file_count,
                source_file_count=source_file_count,
                architecture_layers=list(layers or []),
            ),
            dependencies=DependencyFacts(manifests=list(manifests or [])),
            cloud=cloud,
        ),
        analyzer_version="test",
    )


def _enabled(plan, pack_id: PackId) -> bool:
    record = plan.record_for(pack_id)
    assert record is not None
    return record.enabled


def test_java_repository_activates_core_packs() -> None:
    analysis = _analysis(
        name="java-app",
        files=["pom.xml", "src/main/java/App.java", "src/test/java/AppTest.java"],
        languages=["Java"],
        has_tests=True,
        test_file_count=1,
        source_file_count=20,
        layers=["api", "service"],
        manifests=[
            DependencyManifest(
                path="pom.xml",
                ecosystem="maven",
                manifest_type="pom",
            )
        ],
        cloud=CloudReadinessFacts(has_docker=True),
    )
    plan = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    assert _enabled(plan, PackId.SECURITY) is True
    assert _enabled(plan, PackId.DEPENDENCY) is True
    assert _enabled(plan, PackId.ARCHITECTURE) is True
    assert _enabled(plan, PackId.TECHNICAL_DEBT) is True
    assert _enabled(plan, PackId.TESTING) is True
    assert _enabled(plan, PackId.CLOUD) is True
    assert _enabled(plan, PackId.AI_READINESS) is False
    assert _enabled(plan, PackId.PERFORMANCE) is False
    assert _enabled(plan, PackId.ROADMAP) is True


def test_javascript_repository_activates_expected_packs() -> None:
    analysis = _analysis(
        name="js-app",
        files=["package.json", "src/index.js", "src/index.test.js"],
        languages=["JavaScript"],
        has_tests=True,
        test_file_count=1,
        source_file_count=12,
        manifests=[
            DependencyManifest(
                path="package.json",
                ecosystem="npm",
                manifest_type="package",
            )
        ],
    )
    plan = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    assert _enabled(plan, PackId.SECURITY) is True
    assert _enabled(plan, PackId.DEPENDENCY) is True
    assert _enabled(plan, PackId.TECHNICAL_DEBT) is True
    assert _enabled(plan, PackId.TESTING) is True
    assert _enabled(plan, PackId.CLOUD) is False
    assert _enabled(plan, PackId.PERFORMANCE) is False


def test_python_repository_activates_expected_packs() -> None:
    analysis = _analysis(
        name="py-app",
        files=["requirements.txt", "app/main.py", "tests/test_main.py"],
        languages=["Python"],
        has_tests=True,
        test_file_count=1,
        source_file_count=10,
        manifests=[
            DependencyManifest(
                path="requirements.txt",
                ecosystem="pip",
                manifest_type="requirements",
            )
        ],
    )
    plan = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    assert _enabled(plan, PackId.DEPENDENCY) is True
    assert _enabled(plan, PackId.TECHNICAL_DEBT) is True
    assert _enabled(plan, PackId.TESTING) is True
    assert _enabled(plan, PackId.AI_READINESS) is False


def test_repository_without_cloud_skips_cloud_pack() -> None:
    analysis = _analysis(
        name="no-cloud",
        files=["package.json", "src/index.js"],
        languages=["JavaScript"],
        manifests=[
            DependencyManifest(
                path="package.json",
                ecosystem="npm",
                manifest_type="package",
            )
        ],
        cloud=None,
    )
    plan = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    assert _enabled(plan, PackId.CLOUD) is False
    record = plan.record_for(PackId.CLOUD)
    assert record is not None
    assert "No cloud" in record.reason


def test_repository_with_cloud_enables_cloud_pack() -> None:
    analysis = _analysis(
        name="with-cloud",
        files=["Dockerfile", "package.json"],
        languages=["JavaScript"],
        manifests=[
            DependencyManifest(
                path="package.json",
                ecosystem="npm",
                manifest_type="package",
            )
        ],
        cloud=CloudReadinessFacts(has_docker=True, has_kubernetes=True),
    )
    plan = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    assert _enabled(plan, PackId.CLOUD) is True
    record = plan.record_for(PackId.CLOUD)
    assert record is not None
    assert any("cloud:has_docker" in item for item in record.evidence)


def test_explicit_toml_override_wins(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [assessment]
        activation = "default"

        [rules.security]
        enabled = false

        [assessment.sections.security]
        enabled = false

        [report.sections.security]
        enabled = false

        [rules.performance]
        enabled = true

        [analysis.performance]
        enabled = true

        [report.sections.performance]
        enabled = true
        """,
        encoding="utf-8",
    )
    overrides = collect_explicit_activation_overrides(load_raw_toml_dict(config))
    analysis = _analysis(
        name="override-app",
        files=["pom.xml", "src/main/java/App.java"],
        languages=["Java"],
        source_file_count=20,
        layers=["api"],
        manifests=[
            DependencyManifest(path="pom.xml", ecosystem="maven", manifest_type="pom")
        ],
    )
    plan = build_activation_plan(
        analysis,
        mode=AssessmentActivationMode.DEFAULT,
        overrides=overrides,
    )
    assert _enabled(plan, PackId.SECURITY) is False
    assert plan.record_for(PackId.SECURITY).decision.value == "forced_off"
    assert _enabled(plan, PackId.PERFORMANCE) is True
    assert plan.record_for(PackId.PERFORMANCE).decision.value == "forced_on"

    settings = load_settings(config)
    updated = apply_activation_plan(settings, plan, overrides=overrides)
    assert updated.rules.security.enabled is False
    assert updated.rules.performance.enabled is True


def test_activation_plan_is_deterministic() -> None:
    analysis = _analysis(
        name="stable",
        files=["pom.xml", "Dockerfile", "src/test/java/A.java"],
        languages=["Java"],
        has_tests=True,
        test_file_count=2,
        source_file_count=30,
        layers=["domain", "api"],
        frameworks=["Spring Boot"],
        manifests=[
            DependencyManifest(path="pom.xml", ecosystem="maven", manifest_type="pom")
        ],
        cloud=CloudReadinessFacts(has_docker=True),
    )
    first = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    second = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.to_coverage_payload() == second.to_coverage_payload()


def test_ai_framework_enables_ai_readiness() -> None:
    analysis = _analysis(
        name="ai-app",
        files=["requirements.txt", "app.py"],
        languages=["Python"],
        frameworks=["LangChain", "OpenAI"],
        manifests=[
            DependencyManifest(
                path="requirements.txt",
                ecosystem="pip",
                manifest_type="requirements",
            )
        ],
    )
    plan = build_activation_plan(analysis, mode=AssessmentActivationMode.DEFAULT)
    assert _enabled(plan, PackId.AI_READINESS) is True


def test_collect_repository_evidence_uses_existing_facts_only() -> None:
    analysis = _analysis(
        name="evidence",
        files=["package.json"],
        languages=["TypeScript"],
        manifests=[
            DependencyManifest(
                path="package.json",
                ecosystem="npm",
                manifest_type="package",
            )
        ],
    )
    signals = collect_repository_evidence(analysis)
    assert signals.has_dependency_manifests is True
    assert signals.has_td_eligible_language is True
    assert signals.has_cloud is False
