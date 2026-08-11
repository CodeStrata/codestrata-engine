"""Epic 3 Slice 3.2 — Technology Inventory section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from codestrata.models import (
    AnalysisResult,
    Repository,
    RepositoryFacts,
    Technology,
)
from codestrata.models.build_facts import BuildFacts
from codestrata.models.dependency_facts import DependencyFacts, DependencyManifest
from codestrata.models.enums import TechnologyCategory
from codestrata.models.normalized_facts import StructureFacts
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.technology import (
    build_technology_inventory,
    category_group_id,
)


def _analysis(
    tmp_path: Path,
    *,
    technologies: list[Technology] | None = None,
    structure: StructureFacts | None = None,
    build: BuildFacts | None = None,
    dependencies: DependencyFacts | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["src/App.py", "pom.xml"],
            total_files=2,
        ),
        technologies=technologies or [],
        facts=RepositoryFacts(
            structure=structure
            or StructureFacts(
                file_count=10,
                source_file_count=7,
                test_file_count=3,
                application_count=1,
            ),
            build=build,
            dependencies=dependencies,
        ),
        findings=[],
        recommendations=[],
    )


def test_category_group_mapping() -> None:
    assert category_group_id(TechnologyCategory.LANGUAGE) == "languages"
    assert category_group_id(TechnologyCategory.FRAMEWORK) == "frameworks_libraries"
    assert category_group_id(TechnologyCategory.BUILD_TOOL) == "build_package"
    assert category_group_id(TechnologyCategory.RUNTIME) == "runtime_platform"


def test_inventory_groups_and_omits_empty(tmp_path: Path) -> None:
    analysis = _analysis(
        tmp_path,
        technologies=[
            Technology(
                name="Python",
                category=TechnologyCategory.LANGUAGE,
                version="3.12",
                confidence=0.95,
                source="pyproject.toml",
            ),
            Technology(
                name="FastAPI",
                category=TechnologyCategory.FRAMEWORK,
                version="0.110.0",
                confidence=0.9,
                source="pyproject.toml",
            ),
            Technology(
                name="pip",
                category=TechnologyCategory.BUILD_TOOL,
                version=None,
                confidence=0.7,
                source="requirements.txt",
            ),
        ],
    )
    inventory = build_technology_inventory(analysis)
    group_ids = [group.group_id for group in inventory.groups]
    assert "languages" in group_ids
    assert "frameworks_libraries" in group_ids
    assert "build_package" in group_ids
    assert "runtime_platform" not in group_ids  # empty omitted
    assert inventory.status == "inventory_generated"
    assert inventory.confidence in {"high", "moderate", "limited"}
    assert any("not an assessment of modernity" in note.lower() for note in inventory.limitations)


def test_dedupe_preserves_strongest_version_and_conflicts(tmp_path: Path) -> None:
    analysis = _analysis(
        tmp_path,
        technologies=[
            Technology(
                id=uuid4(),
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                version="17",
                confidence=0.6,
                source="pom.xml",
            ),
            Technology(
                id=uuid4(),
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                version="17",
                confidence=0.95,
                source="build.gradle",
            ),
            Technology(
                id=uuid4(),
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                version="11",
                confidence=0.8,
                source="Dockerfile",
            ),
        ],
    )
    inventory = build_technology_inventory(analysis)
    java_facts = [
        fact
        for group in inventory.groups
        for fact in group.facts
        if fact.name.lower() == "java"
    ]
    versions = sorted({fact.version for fact in java_facts if fact.version})
    assert versions == ["11", "17"]
    assert any(fact.version_state == "conflicting" for fact in java_facts)
    # Exact 17 row keeps the stronger confidence after merge of identical versions.
    seventeen = next(fact for fact in java_facts if fact.version == "17")
    assert seventeen.confidence == 0.95


def test_version_states(tmp_path: Path) -> None:
    analysis = _analysis(
        tmp_path,
        technologies=[
            Technology(
                name="Node.js",
                category=TechnologyCategory.RUNTIME,
                version="20.11.0",
                confidence=0.9,
            ),
            Technology(
                name="lodash",
                category=TechnologyCategory.LIBRARY,
                version="^4.17.0",
                confidence=0.8,
            ),
            Technology(
                name="Make",
                category=TechnologyCategory.BUILD_TOOL,
                version=None,
                confidence=0.5,
            ),
        ],
    )
    inventory = build_technology_inventory(analysis)
    by_name = {
        fact.name: fact
        for group in inventory.groups
        for fact in group.facts
    }
    assert by_name["Node.js"].version_state == "exact"
    assert by_name["lodash"].version_state == "range"
    assert by_name["Make"].version_state == "unavailable"


def test_ecosystems_and_composition(tmp_path: Path) -> None:
    analysis = _analysis(
        tmp_path,
        technologies=[
            Technology(name="Java", category=TechnologyCategory.LANGUAGE, version="17"),
        ],
        build=BuildFacts(
            build_systems=["maven"],
            build_files=["pom.xml"],
            modules=["api", "core"],
        ),
        dependencies=DependencyFacts(
            manifests=[
                DependencyManifest(
                    path="pom.xml",
                    ecosystem="maven",
                    manifest_type="pom",
                )
            ]
        ),
    )
    inventory = build_technology_inventory(analysis)
    eco = next(group for group in inventory.groups if group.group_id == "dependency_ecosystems")
    assert eco.facts[0].name == "maven"
    assert "pom.xml" in eco.facts[0].evidence_paths
    assert inventory.composition is not None
    assert inventory.composition.source_files == 7
    assert inventory.composition.test_files == 3
    assert "api" in inventory.composition.modules
    assert "scanned" in inventory.composition.scope_note.lower() or "scan" in inventory.composition.scope_note.lower()


def test_build_systems_from_build_facts(tmp_path: Path) -> None:
    analysis = _analysis(
        tmp_path,
        technologies=[],
        build=BuildFacts(build_systems=["gradle"], build_files=["build.gradle"]),
    )
    inventory = build_technology_inventory(analysis)
    build_group = next(group for group in inventory.groups if group.group_id == "build_package")
    assert any(fact.name.lower() == "gradle" for fact in build_group.facts)


def test_absolute_paths_stripped_from_evidence(tmp_path: Path) -> None:
    analysis = _analysis(
        tmp_path,
        technologies=[
            Technology(
                name="Python",
                category=TechnologyCategory.LANGUAGE,
                version="3.12",
                source="/abs/secret/pyproject.toml",
            )
        ],
        dependencies=DependencyFacts(
            manifests=[
                DependencyManifest(
                    path="/abs/package.json",
                    ecosystem="npm",
                    manifest_type="package",
                ),
                DependencyManifest(
                    path="package.json",
                    ecosystem="npm",
                    manifest_type="package",
                ),
            ]
        ),
    )
    inventory = build_technology_inventory(analysis)
    for group in inventory.groups:
        for fact in group.facts:
            assert all(not path.startswith("/") for path in fact.evidence_paths)
            assert fact.source is None or not str(fact.source).startswith("/")
    if inventory.composition is not None:
        assert all(not path.startswith("/") for path in inventory.composition.manifest_paths)


def test_html_technology_inventory_section(tmp_path: Path) -> None:
    report_input = ModernizationReportInput(
        analysis_result=_analysis(
            tmp_path,
            technologies=[
                Technology(
                    name="TypeScript",
                    category=TechnologyCategory.LANGUAGE,
                    version="5.4.0",
                    confidence=0.92,
                    source="package.json",
                ),
                Technology(
                    name="Angular",
                    category=TechnologyCategory.FRAMEWORK,
                    version="17.0.0",
                    confidence=0.88,
                    source="package.json",
                ),
            ],
            dependencies=DependencyFacts(
                manifests=[
                    DependencyManifest(
                        path="package.json",
                        ecosystem="npm",
                        manifest_type="package",
                    )
                ]
            ),
        ),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )
    document = build_html_report_view_model(report_input)
    assert document.technology_inventory is not None
    assert document.technology_inventory.fact_count >= 2
    html = HtmlReportRenderer().render(document)
    assert 'id="technology-inventory"' in html
    assert "Languages" in html
    assert "Frameworks and major libraries" in html
    assert "TypeScript" in html
    assert "Exact detected version" in html
    assert "Repository composition" in html
    assert "Limitations" in html
    assert 'data-canonical="coverage-confidence-limitations"' in html or "Coverage" in html
    assert "Modern technology stack" not in html
    assert "Cloud-native" not in html
    assert "Production ready" not in html
    assert 'href="file://' not in html
    assert "src=\"file://" not in html
    assert "/Users/" not in html
    tech_head = next(
        head for head in document.assessment_heads if head.head == "technology_inventory"
    )
    assert tech_head.status_label in {
        "Inventory generated",
        "Partial inventory",
        "Inventory unavailable",
    }
    assert 'href="#technology-inventory"' in html
    # Other assessment heads remain present and unchanged in structure.
    for anchor in (
        "architecture-intelligence",
        "technical-debt-intelligence",
        "dependency-intelligence",
        "security-intelligence",
        "cloud-readiness",
        "ai-readiness",
        "modernization-assessment",
    ):
        assert f'id="{anchor}"' in html
        assert f'href="#{anchor}"' in html
