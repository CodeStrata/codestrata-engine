"""Tests for Rule Engine and builtin rules."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.domain.findings import FindingSeverity
from codestrata.models import Repository
from codestrata.services.graph_assessment import GraphAssessmentPipeline
from codestrata.services.rule_engine import (
    RuleEngine,
    builtin_rules,
    rule_context_from_pipeline,
    write_findings_artifact,
)
from codestrata.services.rule_engine.rules.builtin import (
    AngularDetectedRule,
    JavaDetectedRule,
    LargeRepositoryRule,
    MissingLicenseRule,
    MissingReadmeRule,
    MissingTestsRule,
    NestJsDetectedRule,
    NextJsDetectedRule,
    NodeEngineDetectedRule,
    NpmLockfileMissingRule,
    OutdatedNestJsVersionRule,
    OutdatedNextJsVersionRule,
    OutdatedReactVersionRule,
    OutdatedSvelteVersionRule,
    ReactDetectedRule,
    SpringBootDetectedRule,
    SvelteDetectedRule,
    UnsupportedAngularVersionRule,
    UnsupportedSpringBootVersionRule,
    UnsupportedVueVersionRule,
    VueDetectedRule,
)


def _write_js(root: Path, *, readme: bool = True, license: bool = False) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "js-app",
                "version": "1.0.0",
                "engines": {"node": ">=18"},
                "dependencies": {"express": "^4.0.0"},
            }
        ),
        encoding="utf-8",
    )
    src = root / "src"
    src.mkdir(exist_ok=True)
    (src / "index.js").write_text("console.log('ok');\n", encoding="utf-8")
    files = ["package.json", "src/index.js"]
    if readme:
        (root / "README.md").write_text("# app\n", encoding="utf-8")
        files.append("README.md")
    if license:
        (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        files.append("LICENSE")
    return Repository(name="js-app", path=root.resolve(), files=files, total_files=len(files))


def _write_java(root: Path) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pom.xml").write_text(
        """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter</artifactId>
      <version>2.7.18</version>
    </dependency>
  </dependencies>
</project>
""",
        encoding="utf-8",
    )
    src = root / "src" / "main" / "java" / "demo"
    src.mkdir(parents=True)
    (src / "App.java").write_text("package demo; class App {}", encoding="utf-8")
    files = [
        "pom.xml",
        "src/main/java/demo/App.java",
    ]
    return Repository(name="java-app", path=root.resolve(), files=files, total_files=len(files))


def test_builtin_rule_count() -> None:
    assert len(builtin_rules()) >= 5


def test_missing_readme_and_license_rules(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app", readme=False, license=False)
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    readme = MissingReadmeRule().evaluate(context)
    license_result = MissingLicenseRule().evaluate(context)
    assert len(readme.findings) == 1
    assert len(license_result.findings) == 1


def test_missing_tests_rule(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    result = MissingTestsRule().evaluate(context)
    assert len(result.findings) == 1
    assert result.findings[0].severity is FindingSeverity.MEDIUM


def test_npm_lockfile_missing(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    result = NpmLockfileMissingRule().evaluate(context)
    assert len(result.findings) == 1


def test_node_engine_detected(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    result = NodeEngineDetectedRule().evaluate(context)
    assert len(result.findings) == 1
    assert result.findings[0].metadata.get("node_engine") == ">=18"


def test_large_repository_threshold(tmp_path: Path) -> None:
    root = tmp_path / "big"
    root.mkdir()
    files: list[str] = []
    for index in range(LargeRepositoryRule.THRESHOLD + 1):
        name = f"f{index}.txt"
        (root / name).write_text("x\n", encoding="utf-8")
        files.append(name)
    repository = Repository(name="big", path=root, files=files, total_files=len(files))
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    result = LargeRepositoryRule().evaluate(context)
    assert len(result.findings) == 1


def test_java_and_spring_boot_rules_on_java_sample(tmp_path: Path) -> None:
    repository = _write_java(tmp_path / "java")
    pipeline = GraphAssessmentPipeline().run(repository)
    context = rule_context_from_pipeline(pipeline)
    java_result = JavaDetectedRule().evaluate(context)
    spring_result = SpringBootDetectedRule().evaluate(context)
    unsupported = UnsupportedSpringBootVersionRule().evaluate(context)
    assert len(java_result.findings) == 1
    assert len(spring_result.findings) == 1
    assert spring_result.findings[0].metadata.get("spring_boot_version") == "2.7.18"
    assert len(unsupported.findings) == 1
    assert "spring-boot" in context.bound_keys()


def test_rule_engine_ordering_and_dedup(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app", readme=False)
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    engine = RuleEngine()
    first = engine.evaluate(context)
    second = engine.evaluate(context)
    assert [item.id for item in first.findings] == [item.id for item in second.findings]
    assert first.findings == tuple(
        sorted(first.findings, key=lambda item: (item.rule_id, item.id, item.title))
    )
    ids = [item.id for item in first.findings]
    assert len(ids) == len(set(ids))


def test_empty_assessment_graph_still_evaluates_inventory_rules(tmp_path: Path) -> None:
    root = tmp_path / "emptyish"
    root.mkdir()
    (root / "notes.txt").write_text("hi\n", encoding="utf-8")
    repository = Repository(name="emptyish", path=root, files=["notes.txt"], total_files=1)
    evaluation = RuleEngine().evaluate_pipeline_result(GraphAssessmentPipeline().run(repository))
    assert evaluation.finding_count >= 1
    assert evaluation.rules_evaluated


def test_no_graph_mutation(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    pipeline = GraphAssessmentPipeline().run(repository)
    before_ag = pipeline.assessment_graph.snapshot.model_dump(mode="json")
    before_rg = pipeline.repository_graph.snapshot.model_dump(mode="json")
    before_ekg = pipeline.knowledge_graph.snapshot.model_dump(mode="json")
    RuleEngine().evaluate_pipeline_result(pipeline)
    assert pipeline.assessment_graph.snapshot.model_dump(mode="json") == before_ag
    assert pipeline.repository_graph.snapshot.model_dump(mode="json") == before_rg
    assert pipeline.knowledge_graph.snapshot.model_dump(mode="json") == before_ekg


def test_findings_artifact_stable(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app", readme=False)
    evaluation = RuleEngine().evaluate_pipeline_result(GraphAssessmentPipeline().run(repository))
    first = write_findings_artifact(evaluation, tmp_path / "run-a")
    second = write_findings_artifact(evaluation, tmp_path / "run-b")
    assert first.path.read_bytes() == second.path.read_bytes()
    payload = json.loads(first.path.read_text(encoding="utf-8"))
    assert payload["finding_count"] == evaluation.finding_count
    assert "findings" in payload


def test_javascript_sample_fixture_produces_rule_findings() -> None:
    repo_root = Path(__file__).resolve().parents[4] / "test-fixtures" / "sample-js-app"
    assert repo_root.is_dir()
    files = ["package.json", "README.md", "src/index.js"]
    repository = Repository(
        name="sample-js-app",
        path=repo_root,
        files=files,
        total_files=len(files),
    )
    evaluation = RuleEngine().evaluate_pipeline_result(GraphAssessmentPipeline().run(repository))
    rule_ids = {item.rule_id for item in evaluation.findings}
    assert "codestrata-rule-missing-license" in rule_ids
    assert "codestrata-rule-npm-lockfile-missing" in rule_ids
    assert evaluation.finding_count >= 2


def test_angular_detected_and_unsupported_rules(tmp_path: Path) -> None:
    root = tmp_path / "angular-app"
    root.mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "sales-portal",
                "dependencies": {
                    "@angular/core": "^15.2.0",
                    "@angular/common": "^15.2.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "angular.json").write_text("{}", encoding="utf-8")
    (root / "README.md").write_text("# Sales Portal\n", encoding="utf-8")
    files = ["package.json", "angular.json", "README.md"]
    repo = Repository(
        name="sales-portal", path=root.resolve(), files=files, total_files=len(files)
    )
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    detected = AngularDetectedRule().evaluate(context)
    unsupported = UnsupportedAngularVersionRule().evaluate(context)
    assert len(detected.findings) == 1
    assert "15.2.0" in detected.findings[0].title
    assert len(unsupported.findings) == 1
    assert "Unsupported Angular" in unsupported.findings[0].title


def test_react_detected_and_outdated_rules(tmp_path: Path) -> None:
    root = tmp_path / "react-app"
    root.mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "react-dashboard",
                "dependencies": {
                    "react": "^17.0.2",
                    "react-dom": "^17.0.2",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# React Dashboard\n", encoding="utf-8")
    files = ["package.json", "README.md"]
    repo = Repository(
        name="react-dashboard", path=root.resolve(), files=files, total_files=len(files)
    )
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    detected = ReactDetectedRule().evaluate(context)
    outdated = OutdatedReactVersionRule().evaluate(context)
    assert len(detected.findings) == 1
    assert "17.0.2" in detected.findings[0].title
    assert len(outdated.findings) == 1
    assert "Outdated React" in outdated.findings[0].title


def test_vue_detected_and_unsupported_rules(tmp_path: Path) -> None:
    root = tmp_path / "vue-app"
    root.mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "vue-legacy",
                "dependencies": {
                    "vue": "^2.7.14",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Vue Legacy\n", encoding="utf-8")
    files = ["package.json", "README.md"]
    repo = Repository(
        name="vue-legacy", path=root.resolve(), files=files, total_files=len(files)
    )
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    detected = VueDetectedRule().evaluate(context)
    unsupported = UnsupportedVueVersionRule().evaluate(context)
    assert len(detected.findings) == 1
    assert "2.7.14" in detected.findings[0].title
    assert len(unsupported.findings) == 1
    assert "Unsupported Vue 2" in unsupported.findings[0].title


def test_nextjs_detected_and_outdated_rules(tmp_path: Path) -> None:
    root = tmp_path / "next-app"
    root.mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "next-pages-app",
                "dependencies": {
                    "next": "^12.3.4",
                    "react": "^18.2.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Next Pages App\n", encoding="utf-8")
    files = ["package.json", "README.md"]
    repo = Repository(
        name="next-pages-app", path=root.resolve(), files=files, total_files=len(files)
    )
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    detected = NextJsDetectedRule().evaluate(context)
    outdated = OutdatedNextJsVersionRule().evaluate(context)
    assert len(detected.findings) == 1
    assert "12.3.4" in detected.findings[0].title
    assert len(outdated.findings) == 1
    assert "Outdated Next.js" in outdated.findings[0].title


def test_nestjs_detected_and_outdated_rules(tmp_path: Path) -> None:
    root = tmp_path / "nest-app"
    root.mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "nest-api",
                "dependencies": {
                    "@nestjs/core": "^8.4.7",
                    "@nestjs/common": "^8.4.7",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Nest API\n", encoding="utf-8")
    files = ["package.json", "README.md"]
    repo = Repository(
        name="nest-api", path=root.resolve(), files=files, total_files=len(files)
    )
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    detected = NestJsDetectedRule().evaluate(context)
    outdated = OutdatedNestJsVersionRule().evaluate(context)
    assert len(detected.findings) == 1
    assert "8.4.7" in detected.findings[0].title
    assert len(outdated.findings) == 1
    assert "Outdated NestJS" in outdated.findings[0].title


def test_svelte_detected_and_outdated_rules(tmp_path: Path) -> None:
    root = tmp_path / "svelte-app"
    root.mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "svelte-app",
                "dependencies": {
                    "svelte": "^3.59.2",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Svelte App\n", encoding="utf-8")
    files = ["package.json", "README.md"]
    repo = Repository(
        name="svelte-app", path=root.resolve(), files=files, total_files=len(files)
    )
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    detected = SvelteDetectedRule().evaluate(context)
    outdated = OutdatedSvelteVersionRule().evaluate(context)
    assert len(detected.findings) == 1
    assert "3.59.2" in detected.findings[0].title
    assert len(outdated.findings) == 1
    assert "Outdated Svelte" in outdated.findings[0].title
