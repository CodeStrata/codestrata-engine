"""Tests for the Phase 3 Recommendation Engine."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingSeverity,
    RuleEvaluationResult,
)
from codestrata.domain.recommendations import RecommendationPriority
from codestrata.models import Repository
from codestrata.services.graph_assessment import GraphAssessmentPipeline
from codestrata.services.recommendations import (
    RecommendationContext,
    RecommendationEngine,
    priority_from_finding_severity,
    write_recommendations_artifact,
)
from codestrata.services.rule_engine import RuleEngine, rule_context_from_pipeline


def _write_js(root: Path, *, with_engines: bool = False) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "name": "js-app",
        "version": "1.0.0",
        "dependencies": {"express": "^4.0.0"},
    }
    if with_engines:
        payload["engines"] = {"node": ">=18"}
    (root / "package.json").write_text(json.dumps(payload), encoding="utf-8")
    src = root / "src"
    src.mkdir(exist_ok=True)
    (src / "index.js").write_text("console.log('ok');\n", encoding="utf-8")
    return Repository(
        name="js-app",
        path=root.resolve(),
        files=["package.json", "src/index.js"],
        total_files=2,
    )


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
    return Repository(
        name="java-app",
        path=root.resolve(),
        files=["pom.xml", "src/main/java/demo/App.java"],
        total_files=2,
    )


def _evaluate(repository: Repository):
    pipeline = GraphAssessmentPipeline().run(repository)
    rule_evaluation = RuleEngine().evaluate_pipeline_result(pipeline)
    context = RecommendationContext.from_rule_evaluation(
        rule_context=rule_context_from_pipeline(pipeline),
        evaluation=rule_evaluation,
    )
    result = RecommendationEngine().evaluate(context)
    return pipeline, rule_evaluation, context, result


def test_priority_mapping() -> None:
    assert (
        priority_from_finding_severity(FindingSeverity.CRITICAL) is RecommendationPriority.IMMEDIATE
    )
    assert priority_from_finding_severity(FindingSeverity.HIGH) is RecommendationPriority.HIGH
    assert priority_from_finding_severity(FindingSeverity.MEDIUM) is RecommendationPriority.MEDIUM
    assert priority_from_finding_severity(FindingSeverity.LOW) is RecommendationPriority.LOW
    assert (
        priority_from_finding_severity(FindingSeverity.INFORMATIONAL) is RecommendationPriority.LOW
    )


def test_empty_findings_produce_no_recommendations(tmp_path: Path) -> None:
    root = tmp_path / "emptyish"
    root.mkdir()
    (root / "notes.txt").write_text("hi\n", encoding="utf-8")
    repository = Repository(name="emptyish", path=root, files=["notes.txt"], total_files=1)
    pipeline = GraphAssessmentPipeline().run(repository)
    evaluation = RuleEvaluationResult.from_findings(
        findings=(),
        rules_evaluated=(),
        rules_skipped=(),
    )
    result = RecommendationEngine().evaluate_from_rule_result(
        rule_context=rule_context_from_pipeline(pipeline),
        evaluation=evaluation,
    )
    assert result.recommendation_count == 0
    assert result.recommendations == ()


def test_unknown_finding_type_is_unmatched(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    pipeline = GraphAssessmentPipeline().run(repository)
    orphan = Finding.create(
        rule_id="codestrata-rule-unknown-future",
        title="Unknown",
        description="No provider.",
        severity=FindingSeverity.LOW,
        category=FindingCategory.UNKNOWN,
        subject_keys=("orphan",),
    )
    evaluation = RuleEvaluationResult.from_findings(
        findings=(orphan,),
        rules_evaluated=("codestrata-rule-unknown-future",),
    )
    result = RecommendationEngine().evaluate_from_rule_result(
        rule_context=rule_context_from_pipeline(pipeline),
        evaluation=evaluation,
    )
    assert result.recommendation_count == 0
    assert orphan.id in result.unmatched_finding_ids


def test_javascript_sample_recommendations(tmp_path: Path) -> None:
    _, rule_evaluation, _, result = _evaluate(_write_js(tmp_path / "app", with_engines=False))
    provider_ids = {item.provider_id for item in result.recommendations}
    assert "codestrata-rec-missing-tests" in provider_ids
    assert "codestrata-rec-npm-lockfile-missing" in provider_ids
    assert "codestrata-rec-missing-node-engine" in provider_ids
    assert "codestrata-rec-missing-ci-workflow" in provider_ids
    finding_ids = {item.id for item in rule_evaluation.findings}
    for recommendation in result.recommendations:
        assert set(recommendation.related_finding_ids).issubset(finding_ids)


def test_java_sample_recommendations(tmp_path: Path) -> None:
    _, rule_evaluation, _, result = _evaluate(_write_java(tmp_path / "java"))
    provider_ids = {item.provider_id for item in result.recommendations}
    assert "codestrata-rec-unsupported-spring-boot" in provider_ids
    assert "codestrata-rec-java-language-level" in provider_ids
    assert "codestrata-rec-maven-wrapper-missing" in provider_ids
    boot = next(
        item
        for item in result.recommendations
        if item.provider_id == "codestrata-rec-unsupported-spring-boot"
    )
    assert boot.priority is RecommendationPriority.HIGH
    assert len(boot.actions) >= 5
    finding_ids = {item.id for item in rule_evaluation.findings}
    assert set(boot.related_finding_ids).issubset(finding_ids)


def test_deduplication_and_stable_ordering(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    first = _evaluate(repository)[3]
    second = _evaluate(repository)[3]
    assert [item.id for item in first.recommendations] == [
        item.id for item in second.recommendations
    ]
    ids = [item.id for item in first.recommendations]
    assert len(ids) == len(set(ids))


def test_no_graph_or_finding_mutation(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    pipeline = GraphAssessmentPipeline().run(repository)
    rule_evaluation = RuleEngine().evaluate_pipeline_result(pipeline)
    before_ag = pipeline.assessment_graph.snapshot.model_dump(mode="json")
    before_rg = pipeline.repository_graph.snapshot.model_dump(mode="json")
    before_findings = rule_evaluation.model_dump(mode="json")
    RecommendationEngine().evaluate_pipeline_result(
        pipeline_result=pipeline,
        evaluation=rule_evaluation,
    )
    assert pipeline.assessment_graph.snapshot.model_dump(mode="json") == before_ag
    assert pipeline.repository_graph.snapshot.model_dump(mode="json") == before_rg
    assert rule_evaluation.model_dump(mode="json") == before_findings


def test_recommendations_artifact_stable(tmp_path: Path) -> None:
    _, _, _, result = _evaluate(_write_js(tmp_path / "app"))
    first = write_recommendations_artifact(result, tmp_path / "run-a")
    second = write_recommendations_artifact(result, tmp_path / "run-b")
    assert first.path.read_bytes() == second.path.read_bytes()
    payload = json.loads(first.path.read_text(encoding="utf-8"))
    assert payload["recommendation_count"] == result.recommendation_count
    assert "recommendations" in payload


def test_javascript_fixture_sample() -> None:
    repo_root = Path(__file__).resolve().parents[4] / "test-fixtures" / "sample-js-app"
    files = ["package.json", "README.md", "src/index.js"]
    repository = Repository(
        name="sample-js-app",
        path=repo_root,
        files=files,
        total_files=len(files),
    )
    _, _, _, result = _evaluate(repository)
    provider_ids = {item.provider_id for item in result.recommendations}
    assert "codestrata-rec-npm-lockfile-missing" in provider_ids
    assert "codestrata-rec-missing-node-engine" not in provider_ids
