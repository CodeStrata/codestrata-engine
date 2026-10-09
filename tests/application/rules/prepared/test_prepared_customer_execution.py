"""P03a prepared-package integration. Controlled facts are not repository proof."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from codestrata.application.assessment.service import AssessmentCommandError, run_assessment
from codestrata.application.rules.prepared import (
    BOUNDED_STATIC_PASS_STATEMENT,
    AdmittedPreparedPackage,
    OperatorFactKind,
    OwnerReview,
    PreparedOperatorFacts,
    PreparedPackageError,
    ReviewDecision,
    execute_admitted_customer_rules,
    prepare_reviewed_customer_package,
    preview_customer_package,
    project_python_import_facts,
)
from codestrata.config import CodestrataSettings
from codestrata.domain.contracts.enums import ExecutionPurpose, ResultStatus
from codestrata.domain.contracts.rules import ContractError, parse_effective_ruleset
from codestrata.domain.rules.operators.models import OperatorContext, OperatorEdge, OperatorGraph
from codestrata.models import (
    AnalysisResult,
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
from codestrata.reporting import AssessmentMode
from codestrata.scan_boundary import BoundaryPolicy
from codestrata.services.scanners import LocalRepositoryScanner

OBSERVED_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
VALID_UNTIL = "2027-09-15T00:00:00Z"
RULE_YAML = b"""
api_version: codestrata.io/rules/v1
kind: Rule
metadata:
  id: customer.example.boundary-sample
  version: 1.0.0
  title: Sample boundary
  category: architecture
  owner: Example Owner
applies_to:
  languages: [python]
  facts: [module.declaration, graph.imports]
select:
  source: repository_graph
  nodes:
    all:
    - type: module
condition:
  operator: crosses_boundary
  fact: src/left/**
  value: src/right/**
  edge_types: [imports]
  traversal: direct
  max_depth: 1
  dependency_view: resolved
finding:
  default_severity: high
  message_template: Left imports right
  bindings:
  - name: dependency_path
    type: string
    evidence: dependency_path
evidence_include: [dependency_path]
parameter_schema: []
"""
BOUNDARY_YAML = RULE_YAML.replace(
    b"customer.example.boundary-sample",
    b"customer.example.engine-platform-sample",
).replace(b"src/left/**", b"engine/src/codestrata/**").replace(
    b"src/right/**",
    b"platform/src/codestrata_platform/**",
).replace(b"Sample boundary", b"Engine Platform sample").replace(
    b"Left imports right",
    b"An Engine module directly imports a Platform module",
)
OTHER_YAML = RULE_YAML.replace(
    b"customer.example.boundary-sample",
    b"customer.example.other-sample",
).replace(b"Sample boundary", b"Other boundary")


def _review_for(raw: bytes = RULE_YAML) -> OwnerReview:
    preview = preview_customer_package(
        raw,
        purpose=ExecutionPurpose.PRODUCTION,
        validity_not_after=VALID_UNTIL,
    )
    return OwnerReview(
        reviewer="p03a-integration",
        decision=ReviewDecision.APPROVED,
        plan_digest=preview.plan_digest,
        rule_digest=preview.rule_digest,
        package_digest=preview.package_digest,
    )


def _package(raw: bytes = RULE_YAML):
    return prepare_reviewed_customer_package(
        raw,
        _review_for(raw),
        purpose=ExecutionPurpose.PRODUCTION,
        validity_not_after=VALID_UNTIL,
        observed_at=OBSERVED_AT,
    )


def _imports(*pairs: tuple[str, str], complete: bool = True) -> PreparedOperatorFacts:
    edges = tuple(
        OperatorEdge(source=source, target=target, edge_type="imports") for source, target in pairs
    )
    nodes = tuple(dict.fromkeys(node for pair in pairs for node in pair))
    return PreparedOperatorFacts(
        kind=OperatorFactKind.RESOLVED_IMPORTS,
        context=OperatorContext(
            resolved_graph=OperatorGraph(nodes=nodes, edges=edges, complete=complete)
        ),
    )


def _settings() -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {
            "repository": {"url": "https://github.com/example/sample-app.git", "branch": "main"},
            "workspace": {"directory": ".codestrata-workspace", "clean_before_clone": True},
            "knowledge": {"enabled": False, "directory": ".codestrata-test-knowledge"},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
        }
    )


def _repository(tmp_path: Path) -> Repository:
    root = tmp_path / "sample-app"
    root.mkdir()
    (root / "README.md").write_text("demo\n", encoding="utf-8")
    return Repository(name="sample-app", path=root, files=["README.md"], total_files=1)


def _analysis(repository: Repository) -> AnalysisResult:
    return AnalysisResult(
        repository=repository,
        technologies=[
            Technology(
                name="Python",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="test",
            )
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(file_count=1, source_file_count=1, test_file_count=0)
        ),
        findings=[
            Finding(
                rule_id="SEC001",
                title="Standard finding",
                description="Standard check",
                category=FindingCategory.SECURITY,
                severity=Severity.HIGH,
                source=FindingSource.DETERMINISTIC,
            )
        ],
    )


class _Scanner:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def scan(self, source: str | Path) -> Repository:
        del source
        return self.repository


class _Analysis:
    def __init__(self, result: AnalysisResult) -> None:
        self.result = result

    def analyze(self, repository: Repository, **_: Any) -> AnalysisResult:
        del repository
        return self.result


class _Console:
    def print(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _assess(tmp_path: Path, **kwargs: Any):
    repository = _repository(tmp_path)
    return run_assessment(
        repo=str(repository.path),
        output_directory=tmp_path / "out",
        mode=AssessmentMode.DETERMINISTIC,
        settings=_settings(),
        scanner=_Scanner(repository),
        analysis_service=_Analysis(_analysis(repository)),
        console=_Console(),
        clock=lambda: OBSERVED_AT,
        quiet=True,
        config_path=tmp_path / "missing.toml",
        **kwargs,
    )


def test_platform_preparation_executes_the_reviewed_rule_not_the_example_catalog() -> None:
    package = _package()
    assert package.rule.metadata.id == "customer.example.boundary-sample"
    assert package.example_catalog_substituted is False
    assert package.standard_rules_identity == "python-shared-rules"
    execution = execute_admitted_customer_rules(
        package,
        facts=_imports(("src/left/a.py", "src/right/b.py")),
        observed_at=OBSERVED_AT,
    )
    assert execution.status is ResultStatus.FAIL
    assert execution.rule_id == "customer.example.boundary-sample"
    assert execution.members == ("src/left/a.py->src/right/b.py",)
    assert "architecture.dependency-cycle" not in execution.provenance["rule_id"]


def test_negative_import_does_not_fail_and_pass_is_not_a_finding() -> None:
    package = _package()
    execution = execute_admitted_customer_rules(
        package,
        facts=_imports(("src/left/a.py", "src/left/b.py")),
        observed_at=OBSERVED_AT,
    )
    assert execution.status is ResultStatus.PASS
    from codestrata.application.rules.prepared import findings_for_execution

    assert findings_for_execution(package, execution) == ()


def test_missing_review_rejected_review_and_digest_mismatch_stop_before_admission() -> None:
    with pytest.raises(PreparedPackageError) as missing:
        prepare_reviewed_customer_package(
            RULE_YAML,
            None,
            purpose=ExecutionPurpose.PRODUCTION,
            validity_not_after=VALID_UNTIL,
            observed_at=OBSERVED_AT,
        )
    assert missing.value.code == "review_missing"
    rejected = _review_for().model_copy(update={"decision": ReviewDecision.REJECTED})
    with pytest.raises(PreparedPackageError) as rejected_error:
        prepare_reviewed_customer_package(
            RULE_YAML,
            rejected,
            purpose=ExecutionPurpose.PRODUCTION,
            validity_not_after=VALID_UNTIL,
            observed_at=OBSERVED_AT,
        )
    assert rejected_error.value.code == "review_rejected"
    mismatched = _review_for().model_copy(update={"plan_digest": "0" * 64})
    with pytest.raises(PreparedPackageError) as mismatch:
        prepare_reviewed_customer_package(
            RULE_YAML,
            mismatched,
            purpose=ExecutionPurpose.PRODUCTION,
            validity_not_after=VALID_UNTIL,
            observed_at=OBSERVED_AT,
        )
    assert mismatch.value.code == "review_digest_mismatch"


def test_preview_package_cannot_authorize_production() -> None:
    preview = preview_customer_package(
        RULE_YAML,
        purpose=ExecutionPurpose.PREVIEW,
        validity_not_after=None,
    )
    review = OwnerReview(
        reviewer="p03a-integration",
        decision=ReviewDecision.APPROVED,
        plan_digest=preview.plan_digest,
        rule_digest=preview.rule_digest,
        package_digest=preview.package_digest,
    )
    preview_package = prepare_reviewed_customer_package(
        RULE_YAML,
        review,
        purpose=ExecutionPurpose.PREVIEW,
        validity_not_after=None,
        observed_at=OBSERVED_AT,
    )
    with pytest.raises(PreparedPackageError) as error:
        execute_admitted_customer_rules(
            preview_package,
            facts=_imports(("src/left/a.py", "src/right/b.py")),
            observed_at=OBSERVED_AT,
            requested_purpose=ExecutionPurpose.PRODUCTION,
        )
    assert error.value.code == "preview_cannot_authorize_production"
    allowed = execute_admitted_customer_rules(
        preview_package,
        facts=None,
        observed_at=OBSERVED_AT,
        requested_purpose=ExecutionPurpose.PREVIEW,
    )
    assert allowed.status is ResultStatus.UNKNOWN
    assert allowed.reason == "missing_view"
    payload = preview_package.effective.model_dump(mode="json")
    payload["ruleset_id"] = "tampered.ruleset"
    with pytest.raises(ContractError):
        parse_effective_ruleset(payload)


def test_expired_package_is_not_executed() -> None:
    preview = preview_customer_package(
        RULE_YAML,
        purpose=ExecutionPurpose.PRODUCTION,
        validity_not_after="2020-01-01T00:00:00Z",
    )
    review = OwnerReview(
        reviewer="p03a-integration",
        decision=ReviewDecision.APPROVED,
        plan_digest=preview.plan_digest,
        rule_digest=preview.rule_digest,
        package_digest=preview.package_digest,
    )
    with pytest.raises(PreparedPackageError) as error:
        prepare_reviewed_customer_package(
            RULE_YAML,
            review,
            purpose=ExecutionPurpose.PRODUCTION,
            validity_not_after="2020-01-01T00:00:00Z",
            observed_at=OBSERVED_AT,
        )
    assert error.value.code == "expired"


def test_missing_contains_only_and_incomplete_views_stay_unknown() -> None:
    package = _package()
    missing = execute_admitted_customer_rules(package, facts=None, observed_at=OBSERVED_AT)
    assert missing.status is ResultStatus.UNKNOWN
    assert missing.reason == "missing_view"
    contains = execute_admitted_customer_rules(
        package,
        facts=PreparedOperatorFacts(
            kind=OperatorFactKind.CONTAINS_ONLY,
            context=OperatorContext(
                resolved_graph=OperatorGraph(
                    nodes=("repo:sample:file:README.md",),
                    edges=(
                        OperatorEdge(
                            source="repo:sample",
                            target="repo:sample:file:README.md",
                            edge_type="contains",
                        ),
                    ),
                    complete=True,
                )
            ),
        ),
        observed_at=OBSERVED_AT,
    )
    assert contains.status is ResultStatus.UNKNOWN
    assert contains.reason == "contains_only_graph"
    incomplete = execute_admitted_customer_rules(
        package,
        facts=_imports(("src/left/a.py", "src/left/b.py"), complete=False),
        observed_at=OBSERVED_AT,
    )
    assert incomplete.status is ResultStatus.UNKNOWN
    assert incomplete.reason == "unresolved_relevant_edge"


def test_mixed_package_and_invocation_tampering_are_rejected() -> None:
    first = _package()
    second = _package(OTHER_YAML)
    mixed = AdmittedPreparedPackage.model_construct(
        api=first.api,
        review=second.review,
        effective=first.effective,
        rule=second.rule,
        plan_digest=second.plan_digest,
        source_digest=second.source_digest,
        manifest=first.manifest,
        standard_rules_identity=first.standard_rules_identity,
        example_catalog_substituted=False,
    )
    with pytest.raises(PreparedPackageError) as mixed_error:
        execute_admitted_customer_rules(mixed, facts=None, observed_at=OBSERVED_AT)
    assert mixed_error.value.code == "package_binding_mismatch"
    tampered = AdmittedPreparedPackage.model_construct(
        api=first.api,
        review=first.review,
        effective=first.effective,
        rule=first.rule,
        plan_digest="ab" * 32,
        source_digest=first.source_digest,
        manifest=first.manifest,
        standard_rules_identity=first.standard_rules_identity,
        example_catalog_substituted=False,
    )
    with pytest.raises(PreparedPackageError) as tampered_error:
        execute_admitted_customer_rules(tampered, facts=None, observed_at=OBSERVED_AT)
    assert tampered_error.value.code == "package_binding_mismatch"


def test_run_assessment_rejects_a_preview_package(tmp_path: Path) -> None:
    preview = preview_customer_package(
        RULE_YAML,
        purpose=ExecutionPurpose.PREVIEW,
        validity_not_after=None,
    )
    package = prepare_reviewed_customer_package(
        RULE_YAML,
        OwnerReview(
            reviewer="p03a-integration",
            decision=ReviewDecision.APPROVED,
            plan_digest=preview.plan_digest,
            rule_digest=preview.rule_digest,
            package_digest=preview.package_digest,
        ),
        purpose=ExecutionPurpose.PREVIEW,
        validity_not_after=None,
        observed_at=OBSERVED_AT,
    )
    with pytest.raises(AssessmentCommandError) as error:
        _assess(
            tmp_path,
            prepared_customer_package=package,
            customer_operator_facts=_imports(("src/left/a.py", "src/right/b.py")),
        )
    assert "preview_cannot_authorize_production" in str(error.value)


def test_direct_engine_call_still_requires_the_platform_review_record() -> None:
    with pytest.raises(PreparedPackageError) as error:
        prepare_reviewed_customer_package(
            RULE_YAML,
            None,
            purpose=ExecutionPurpose.PRODUCTION,
            validity_not_after=VALID_UNTIL,
            observed_at=OBSERVED_AT,
        )
    assert error.value.code == "review_missing"


def test_ordinary_assessment_keeps_standard_findings_and_records_the_customer_rule(
    tmp_path: Path,
) -> None:
    package = _package()
    result = _assess(
        tmp_path,
        prepared_customer_package=package,
        customer_operator_facts=_imports(("src/left/a.py", "src/right/b.py")),
    )
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "SEC001" in findings
    assert "customer.example.boundary-sample" in findings
    assert "Sample boundary" in html
    assert package.effective.effective_ruleset_digest in analysis
    assert '"example_catalog_substituted": false' in analysis
    assert "health_score" not in result.json_report_path.read_text(encoding="utf-8")


def test_no_package_path_does_not_add_customer_provenance(tmp_path: Path) -> None:
    result = _assess(tmp_path)
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "SEC001" in findings
    assert "prepared_customer_rules" not in analysis
    assert "customer.example.boundary-sample" not in findings


def test_engine_sources_do_not_import_platform() -> None:
    root = Path(__file__).resolve().parents[4] / "src"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("import codestrata_platform") or stripped.startswith(
                "from codestrata_platform"
            ):
                offenders.append(f"{path}:{stripped}")
    assert offenders == []


def test_assessment_cli_has_no_custom_rule_flag() -> None:
    source = (
        Path(__file__).resolve().parents[4] / "src" / "codestrata" / "cli" / "assess.py"
    ).read_text(encoding="utf-8")
    assert "--custom-rules" not in source
    assert "prepared_customer_package" not in source


def test_invalid_package_fails_the_assessment_instead_of_being_ignored(tmp_path: Path) -> None:
    package = _package()
    stale = package.model_copy(
        update={
            "effective": package.effective.model_copy(
                update={"validity_not_after": "2020-01-01T00:00:00Z"}
            )
        }
    )
    with pytest.raises((PreparedPackageError, AssessmentCommandError, ValueError)):
        _assess(
            tmp_path,
            prepared_customer_package=stale,
            customer_operator_facts=_imports(("src/left/a.py", "src/right/b.py")),
        )


def _tree_repository(tmp_path: Path, files: dict[str, str]) -> Repository:
    root = tmp_path / "sample-app"
    root.mkdir()
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    listed = tuple(files)
    return Repository(name="sample-app", path=root, files=list(listed), total_files=len(listed))


def _assess_tree(tmp_path: Path, files: dict[str, str], **kwargs: Any):
    repository = _tree_repository(tmp_path, files)
    return run_assessment(
        repo=str(repository.path),
        output_directory=tmp_path / "out",
        mode=AssessmentMode.DETERMINISTIC,
        settings=_settings(),
        scanner=_Scanner(repository),
        analysis_service=_Analysis(_analysis(repository)),
        console=_Console(),
        clock=lambda: OBSERVED_AT,
        quiet=True,
        config_path=tmp_path / "missing.toml",
        **kwargs,
    )


def test_projected_engine_to_platform_import_fails_through_run_assessment(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/app.py": "import codestrata_platform.api\n",
        "engine/src/codestrata/__init__.py": "",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_tree(tmp_path, files, prepared_customer_package=package)
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "SEC001" in findings
    assert "customer.example.engine-platform-sample" in findings
    assert "engine/src/codestrata/app.py->platform/src/codestrata_platform/api.py" in findings
    assert package.effective.effective_ruleset_digest in analysis
    assert '"root_discovery": "discovered"' in analysis
    assert "src-or-top-level-package" in analysis
    assert "bounded_static_imports" in analysis


def test_projected_internal_and_reverse_imports_pass_with_bounded_wording(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/app.py": "import codestrata.application\n",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/application/__init__.py": "",
        "platform/src/codestrata_platform/client.py": "import codestrata\n",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_tree(
        tmp_path,
        files,
        prepared_customer_package=package,
        external_import_names=(),
    )
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "SEC001" in findings
    assert "customer.example.engine-platform-sample" not in findings
    assert BOUNDED_STATIC_PASS_STATEMENT in analysis
    assert "not_claimed" in analysis


def test_caller_supplied_facts_override_repository_imports(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/app.py": "import codestrata_platform.api\n",
        "platform/src/codestrata_platform/api.py": "",
    }
    result = _assess_tree(
        tmp_path,
        files,
        prepared_customer_package=package,
        customer_operator_facts=_imports(
            ("engine/src/codestrata/app.py", "engine/src/codestrata/other.py")
        ),
    )
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    assert "customer.example.engine-platform-sample" not in findings


def _write_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "sample-app"
    root.mkdir()
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _assess_real_scan(
    tmp_path: Path,
    files: dict[str, str],
    *,
    max_files: int | None = None,
    boundary_policy: BoundaryPolicy | None = None,
    settings: CodestrataSettings | None = None,
    **kwargs: Any,
):
    root = _write_tree(tmp_path, files)
    scanner = LocalRepositoryScanner(max_files=max_files, boundary_policy=boundary_policy)
    repository = scanner.scan(root)
    return run_assessment(
        repo=str(root),
        output_directory=tmp_path / "out",
        mode=AssessmentMode.DETERMINISTIC,
        settings=settings or _settings(),
        scanner=scanner,
        analysis_service=_Analysis(_analysis(repository)),
        console=_Console(),
        clock=lambda: OBSERVED_AT,
        quiet=True,
        config_path=tmp_path / "missing.toml",
        **kwargs,
    )


def test_truncated_scan_projects_incomplete_coverage_as_unknown(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/app.py": "import codestrata.application\n",
        "engine/src/codestrata/other.py": "import codestrata\n",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/application/__init__.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(tmp_path, files, max_files=1, prepared_customer_package=package)
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    assert "customer.example.engine-platform-sample" in findings
    assert "unresolved_relevant_edge" in analysis
    assert "scan_collection_truncated" in analysis


def test_excluded_python_absent_from_inventory_through_real_scan(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    policy = BoundaryPolicy(
        exclude_paths=("engine/src/codestrata/labeled/hidden.py",),
        production_roots=("engine/src", "platform/src"),
    )
    files = {
        "engine/src/codestrata/app.py": "import codestrata.application\n",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/application/__init__.py": "",
        "engine/src/codestrata/labeled/hidden.py": "import codestrata_platform.api\n",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(
        tmp_path,
        files,
        boundary_policy=policy,
        prepared_customer_package=package,
    )
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "engine/src/codestrata/labeled/hidden.py" in analysis
    assert "excluded_under_root" in analysis
    assert "unresolved_relevant_edge" in analysis


def test_configured_boundary_exclusion_through_ordinary_assessment(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    config = tmp_path / "codestrata.toml"
    config.write_text(
        '[scan]\nexclude_paths = ["engine/src/codestrata/labeled/hidden.py"]\n',
        encoding="utf-8",
    )
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"url": "https://github.com/example/sample-app.git", "branch": "main"},
            "workspace": {"directory": ".codestrata-workspace", "clean_before_clone": True},
            "knowledge": {"enabled": False, "directory": ".codestrata-test-knowledge"},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
            "scan": {"exclude_paths": ["engine/src/codestrata/labeled/hidden.py"]},
        }
    )
    files = {
        "engine/src/codestrata/app.py": "import codestrata.application\n",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/application/__init__.py": "",
        "engine/src/codestrata/labeled/hidden.py": "import codestrata_platform.api\n",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    root = _write_tree(tmp_path, files)
    scanner = LocalRepositoryScanner(
        boundary_policy=BoundaryPolicy.from_settings(settings),
    )
    repository = scanner.scan(root)
    result = run_assessment(
        repo=str(root),
        output_directory=tmp_path / "out-boundary",
        mode=AssessmentMode.DETERMINISTIC,
        settings=settings,
        scanner=scanner,
        analysis_service=_Analysis(_analysis(repository)),
        console=_Console(),
        clock=lambda: OBSERVED_AT,
        quiet=True,
        config_path=config,
        prepared_customer_package=package,
    )
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "excluded_under_root" in analysis
    assert "engine/src/codestrata/labeled/hidden.py" in analysis


def test_complete_negative_fixture_passes_with_bounded_wording_via_real_scan(
    tmp_path: Path,
) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/app.py": "import codestrata.application\n",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/application/__init__.py": "",
        "platform/src/codestrata_platform/client.py": "import codestrata\n",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(tmp_path, files, prepared_customer_package=package)
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "customer.example.engine-platform-sample" not in findings
    assert BOUNDED_STATIC_PASS_STATEMENT in analysis
    assert "collection_truncated" not in analysis or '"collection_truncated": false' in analysis


def test_repository_root_pruned_directory_stays_unknown_for_negative_boundary() -> None:
    package = _package(BOUNDARY_YAML)
    caller = project_python_import_facts(
        ("a.py",),
        {"a.py": ""},
        source_roots=("",),
        pruned_directories=("vendor",),
    )
    caller_result = execute_admitted_customer_rules(
        package,
        facts=caller,
        observed_at=OBSERVED_AT,
    )
    assert any(
        item.code == "pruned_under_root" and item.path == "vendor" for item in caller.limitations
    )
    assert caller.context is not None
    assert caller.context.resolved_graph is not None
    assert caller.context.resolved_graph.complete is False
    assert caller_result.status is ResultStatus.UNKNOWN
    discovered = project_python_import_facts(
        ("a.py",),
        {"a.py": ""},
        pruned_directories=("vendor",),
    )
    discovered_result = execute_admitted_customer_rules(
        package,
        facts=discovered,
        observed_at=OBSERVED_AT,
    )
    assert discovered.root_discovery == "discovered"
    assert "" in discovered.source_roots
    assert any(
        item.code == "pruned_under_root" and item.path == "vendor"
        for item in discovered.limitations
    )
    assert discovered.context is not None
    assert discovered.context.resolved_graph is not None
    assert discovered.context.resolved_graph.complete is False
    assert discovered_result.status is ResultStatus.UNKNOWN


def test_pruned_ancestor_of_caller_root_stays_unknown_for_negative_boundary(
    tmp_path: Path,
) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/a.py": "",
        "engine/src/codestrata/__init__.py": "",
        "platform/src/vendor/pkg/__init__.py": "",
        "platform/src/vendor/hidden.py": "import codestrata_platform.api\n",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(
        tmp_path,
        files,
        prepared_customer_package=package,
        source_roots=("engine/src", "platform/src/vendor/pkg"),
    )
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "platform/src/vendor" in analysis
    assert "pruned_under_root" in analysis
    assert "unresolved_relevant_edge" in analysis


def test_pruned_vendor_under_source_root_stays_unknown_for_negative_boundary(
    tmp_path: Path,
) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/a.py": "",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/vendor/hidden.py": "import codestrata_platform.api\n",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(tmp_path, files, prepared_customer_package=package)
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    assert "engine/src/codestrata/vendor" in analysis
    assert "pruned_under_root" in analysis
    assert "unresolved_relevant_edge" in analysis
    assert (
        "engine/src/codestrata/a.py->platform/src/codestrata_platform/api.py" not in findings
    )


def test_top_level_pruned_vendor_does_not_block_complete_negative_pass(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "vendor/hidden.py": "import codestrata_platform.api\n",
        "engine/src/codestrata/a.py": "",
        "engine/src/codestrata/__init__.py": "",
        "platform/src/codestrata_platform/client.py": "import codestrata\n",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(tmp_path, files, prepared_customer_package=package)
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "customer.example.engine-platform-sample" not in findings
    assert BOUNDED_STATIC_PASS_STATEMENT in analysis
    assert "pruned_under_root" not in analysis


def test_pruned_directory_diagnostics_cap_marks_coverage_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import codestrata.scan_boundary.service as scan_boundary_service

    monkeypatch.setattr(scan_boundary_service, "_MAX_PRUNED_DIRECTORIES", 1)
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/a.py": "",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/node_modules/x.py": "",
        "engine/src/codestrata/vendor/hidden.py": "import codestrata_platform.api\n",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(tmp_path, files, prepared_customer_package=package)
    analysis = (result.run_directory / "analysis-result.json").read_text(encoding="utf-8")
    assert "coverage_diagnostics_capped" in analysis
    assert "unresolved_relevant_edge" in analysis


def test_resolved_crossing_edge_fails_via_real_scan(tmp_path: Path) -> None:
    package = _package(BOUNDARY_YAML)
    files = {
        "engine/src/codestrata/app.py": "import codestrata_platform.api\n",
        "engine/src/codestrata/__init__.py": "",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    result = _assess_real_scan(tmp_path, files, prepared_customer_package=package)
    findings = (result.run_directory / "findings.json").read_text(encoding="utf-8")
    assert "customer.example.engine-platform-sample" in findings
    assert "engine/src/codestrata/app.py->platform/src/codestrata_platform/api.py" in findings


def test_projected_alias_does_not_claim_more_than_bounded_coverage() -> None:
    texts = {
        "engine/src/codestrata/app.py": (
            "import importlib\nload = importlib.import_module\nload('codestrata_platform.api')\n"
        ),
        "engine/src/codestrata/__init__.py": "",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    facts = project_python_import_facts(
        tuple(texts),
        texts,
        source_roots=("engine/src", "platform/src"),
        external_import_names=("importlib",),
    )
    package = _package(BOUNDARY_YAML)
    execution = execute_admitted_customer_rules(package, facts=facts, observed_at=OBSERVED_AT)
    assert execution.status is ResultStatus.PASS
    assert execution.provenance["pass_statement"] == BOUNDED_STATIC_PASS_STATEMENT
    assert "codestrata_platform" not in " ".join(execution.members)
