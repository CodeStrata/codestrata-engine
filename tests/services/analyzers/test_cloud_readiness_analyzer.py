"""Tests for deterministic cloud-readiness analysis."""

from __future__ import annotations

from pathlib import Path

from codestrata.models import Repository
from codestrata.services.analyzers.cloud_readiness_analyzer import (
    CloudReadinessAnalyzer,
)


def _repository(
    root: Path,
    files: list[str],
) -> Repository:
    """Create a repository fixture with empty files."""

    for relative_path in files:
        file_path = root / relative_path
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        file_path.write_text(
            "",
            encoding="utf-8",
        )

    return Repository(
        name=root.name,
        path=root,
        files=files,
    )


def _rule_ids(
    repository: Repository,
) -> set[str]:
    """Run the analyzer and return rule identifiers."""

    result = CloudReadinessAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    return {finding.rule_id for finding in result.findings if finding.rule_id is not None}


def test_detects_dockerfile(
    tmp_path: Path,
) -> None:
    """Dockerfiles should be detected."""

    repository = _repository(
        tmp_path,
        [
            "Dockerfile",
        ],
    )

    rule_ids = _rule_ids(repository)

    assert "CLOUD001" in rule_ids
    assert "CLOUD010" in rule_ids
    assert "CLOUD009" not in rule_ids


def test_detects_named_dockerfile(
    tmp_path: Path,
) -> None:
    """Environment-specific Dockerfiles should be detected."""

    repository = _repository(
        tmp_path,
        [
            "docker/Dockerfile.production",
        ],
    )

    assert "CLOUD001" in _rule_ids(repository)


def test_detects_docker_compose(
    tmp_path: Path,
) -> None:
    """Docker Compose configurations should be detected."""

    repository = _repository(
        tmp_path,
        [
            "docker-compose.yml",
        ],
    )

    assert "CLOUD002" in _rule_ids(repository)


def test_detects_kubernetes_directory(
    tmp_path: Path,
) -> None:
    """YAML files under Kubernetes directories should be detected."""

    repository = _repository(
        tmp_path,
        [
            "k8s/deployment.yaml",
            "k8s/service.yaml",
        ],
    )

    assert "CLOUD003" in _rule_ids(repository)


def test_detects_kubernetes_file_name(
    tmp_path: Path,
) -> None:
    """Kubernetes-style YAML filenames should be detected."""

    repository = _repository(
        tmp_path,
        [
            "deployment.yaml",
        ],
    )

    assert "CLOUD003" in _rule_ids(repository)


def test_does_not_treat_non_yaml_file_as_kubernetes(
    tmp_path: Path,
) -> None:
    """Kubernetes filename markers should require YAML files."""

    repository = _repository(
        tmp_path,
        [
            "deployment.txt",
        ],
    )

    assert "CLOUD003" not in _rule_ids(repository)


def test_detects_helm_chart(
    tmp_path: Path,
) -> None:
    """Helm chart files should be detected."""

    repository = _repository(
        tmp_path,
        [
            "helm/customer-api/Chart.yaml",
            "helm/customer-api/values.yaml",
        ],
    )

    assert "CLOUD004" in _rule_ids(repository)


def test_detects_terraform(
    tmp_path: Path,
) -> None:
    """Terraform files should be detected."""

    repository = _repository(
        tmp_path,
        [
            "infrastructure/main.tf",
            "infrastructure/production.tfvars",
        ],
    )

    assert "CLOUD005" in _rule_ids(repository)


def test_detects_cloudformation(
    tmp_path: Path,
) -> None:
    """CloudFormation files should be detected."""

    repository = _repository(
        tmp_path,
        [
            "infrastructure/cloudformation/application.yaml",
        ],
    )

    assert "CLOUD006" in _rule_ids(repository)


def test_detects_cfn_file(
    tmp_path: Path,
) -> None:
    """CFN naming conventions should be detected."""

    repository = _repository(
        tmp_path,
        [
            "infrastructure/cfn-stack.json",
        ],
    )

    assert "CLOUD006" in _rule_ids(repository)


def test_detects_serverless_framework(
    tmp_path: Path,
) -> None:
    """Serverless Framework configuration should be detected."""

    repository = _repository(
        tmp_path,
        [
            "serverless.yml",
        ],
    )

    assert "CLOUD007" in _rule_ids(repository)


def test_detects_aws_sam_template(
    tmp_path: Path,
) -> None:
    """AWS SAM templates should be detected."""

    repository = _repository(
        tmp_path,
        [
            "template.yaml",
            "samconfig.toml",
        ],
    )

    assert "CLOUD007" in _rule_ids(repository)


def test_detects_deployment_workflow(
    tmp_path: Path,
) -> None:
    """Deployment-oriented GitHub workflows should be detected."""

    repository = _repository(
        tmp_path,
        [
            ".github/workflows/deploy-production.yml",
        ],
    )

    assert "CLOUD008" in _rule_ids(repository)


def test_does_not_treat_build_workflow_as_deployment(
    tmp_path: Path,
) -> None:
    """Build-only workflow names should not imply deployment."""

    repository = _repository(
        tmp_path,
        [
            ".github/workflows/build.yml",
        ],
    )

    assert "CLOUD008" not in _rule_ids(repository)


def test_reports_missing_cloud_assets(
    tmp_path: Path,
) -> None:
    """Repositories without cloud assets should receive a low finding."""

    repository = _repository(
        tmp_path,
        [
            "src/main/java/com/example/Application.java",
            "README.md",
        ],
    )

    rule_ids = _rule_ids(repository)

    assert "CLOUD009" in rule_ids
    assert "CLOUD010" not in rule_ids


def test_creates_readiness_summary_for_multiple_capabilities(
    tmp_path: Path,
) -> None:
    """Detected capabilities should produce a readiness summary."""

    repository = _repository(
        tmp_path,
        [
            "Dockerfile",
            "infrastructure/main.tf",
            "k8s/deployment.yaml",
            ".github/workflows/release.yml",
        ],
    )

    result = CloudReadinessAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    summary = next(finding for finding in result.findings if finding.rule_id == "CLOUD010")

    capabilities = summary.metadata["capabilities"]

    assert "docker" in capabilities
    assert "terraform" in capabilities
    assert "kubernetes" in capabilities
    assert "deployment_workflows" in capabilities
