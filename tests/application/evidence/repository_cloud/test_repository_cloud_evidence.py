"""Repository-cloud evidence tests (Phase 4.7.2)."""

from __future__ import annotations

import ast
import random
from pathlib import Path

from codestrata.application.evidence.repository_cloud.artifacts import (
    repository_cloud_evidence_payload,
    write_repository_cloud_evidence_artifact,
)
from codestrata.application.evidence.repository_cloud.discovery import (
    classify_cloud_candidate,
    discover_cloud_candidates,
    is_ignored_path,
)
from codestrata.application.evidence.repository_cloud.service import (
    RepositoryCloudEvidenceService,
)
from codestrata.config import load_settings
from codestrata.config.settings import RepositoryCloudEvidenceSettings
from codestrata.domain.evidence.repository_cloud.enums import (
    CloudContainerKind,
    CloudDeploymentSystem,
    CloudIaCKind,
    CloudManagedServiceKind,
    CloudOrchestrationKind,
    CloudPlatformKind,
    EvidenceConfirmationLevel,
    RepositoryCloudParseStatus,
)
from codestrata.domain.evidence.repository_cloud.identifiers import (
    REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_CLOUD_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_APP_PACKAGE = Path("src/codestrata/application/evidence/repository_cloud")
_FORBIDDEN_IMPORT_PREFIXES = (
    "codestrata.domain.cloud",
    "codestrata.application.cloud",
    "codestrata.domain.findings",
    "codestrata.application.reporting",
    "codestrata.reporting",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]  # engine root


def test_package_boundary_no_forbidden_imports() -> None:
    package_dir = _repo_root() / _APP_PACKAGE
    assert package_dir.is_dir()
    for path in sorted(package_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    assert not any(
                        mod == prefix or mod.startswith(prefix + ".")
                        for prefix in _FORBIDDEN_IMPORT_PREFIXES
                    ), f"{path.name} imports {mod}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                assert not any(
                    mod == prefix or mod.startswith(prefix + ".")
                    for prefix in _FORBIDDEN_IMPORT_PREFIXES
                ), f"{path.name} imports from {mod}"
        assert "FindingCategory" not in source
        assert "emit_finding" not in source.lower()


def test_defaults_disabled(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.evidence.repository_cloud.enabled is False
    assert settings.analysis.cloud.enabled is False
    assert settings.evidence.repository_testing.enabled is False


def test_configuration_enablement(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [evidence.repository_cloud]
        enabled = true
        max_files = 100
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_cloud.enabled is True
    assert settings.evidence.repository_cloud.max_files == 100
    assert settings.analysis.cloud.enabled is False
    assert settings.evidence.repository_testing.enabled is False


def test_disabled_returns_not_applicable() -> None:
    service = RepositoryCloudEvidenceService(RepositoryCloudEvidenceSettings(enabled=False))
    evidence = service.collect(
        repository_id="repo:x",
        relative_paths=("Dockerfile",),
        file_texts={"Dockerfile": "FROM alpine\n"},
    )
    assert evidence.status is RepositoryCloudParseStatus.NOT_APPLICABLE
    assert evidence.file_candidates == ()


def test_no_cloud_artifacts_succeeds_empty() -> None:
    service = RepositoryCloudEvidenceService(RepositoryCloudEvidenceSettings(enabled=True))
    evidence = service.collect(
        repository_id="repo:plain",
        relative_paths=("src/main.py", "README.md"),
        file_texts={"src/main.py": "print('hi')\n", "README.md": "# app\n"},
    )
    assert evidence.status is RepositoryCloudParseStatus.SUCCEEDED
    assert evidence.file_candidates == ()
    assert evidence.coverage.candidate_files_discovered == 0
    assert evidence.limitations


def test_false_positive_service_py_not_kubernetes() -> None:
    assert classify_cloud_candidate("src/service.py") is None
    assert classify_cloud_candidate("app/Service.java") is None
    assert classify_cloud_candidate(
        "services/registration-service.yaml"
    ) is None
    hit = classify_cloud_candidate("k8s/deployment.yaml")
    assert hit is not None
    assert hit.orchestration_kind is CloudOrchestrationKind.KUBERNETES
    exact = classify_cloud_candidate("manifests/service.yaml")
    assert exact is not None
    assert exact.orchestration_kind is CloudOrchestrationKind.KUBERNETES


def test_discover_sorted_and_ignored() -> None:
    paths = [
        "node_modules/pkg/Dockerfile",
        "Dockerfile",
        "k8s/service.yaml",
        "terraform/main.tf",
    ]
    found = discover_cloud_candidates(paths)
    assert [item.path for item in found] == [
        "Dockerfile",
        "k8s/service.yaml",
        "terraform/main.tf",
    ]
    assert is_ignored_path("node_modules/pkg/Dockerfile", ignore_markers=("/node_modules/",))


def test_collect_docker_terraform_k8s_and_services() -> None:
    service = RepositoryCloudEvidenceService(RepositoryCloudEvidenceSettings(enabled=True))
    paths = (
        "Dockerfile",
        "docker-compose.yml",
        "terraform/main.tf",
        "k8s/deployment.yaml",
        "charts/app/Chart.yaml",
        "serverless.yml",
        ".github/workflows/deploy.yml",
        "infra/main.bicep",
        "Pulumi.yaml",
        "cdk.json",
    )
    texts = {
        "Dockerfile": "FROM public.ecr.aws/lambda/python:3.12\n",
        "docker-compose.yml": "services:\n  api:\n    image: api:latest\n",
        "terraform/main.tf": (
            'provider "aws" {\n  region = "us-east-1"\n}\n'
            'resource "aws_s3_bucket" "data" {\n  bucket = "demo"\n}\n'
            'resource "aws_dynamodb_table" "items" {\n  name = "items"\n'
            '  hash_key = "id"\n  billing_mode = "PAY_PER_REQUEST"\n'
            '  attribute {\n    name = "id"\n    type = "S"\n  }\n}\n'
        ),
        "k8s/deployment.yaml": ("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: api\n"),
        "charts/app/Chart.yaml": "apiVersion: v2\nname: app\nversion: 0.1.0\n",
        "serverless.yml": (
            "service: demo\nprovider:\n  name: aws\nfunctions:\n  hello:\n    handler: h.main\n"
        ),
        ".github/workflows/deploy.yml": (
            "jobs:\n  deploy:\n    steps:\n      - run: helm upgrade --install app ./charts/app\n"
        ),
        "infra/main.bicep": "targetScope = 'resourceGroup'\n",
        "Pulumi.yaml": "name: demo\nruntime: python\n",
        "cdk.json": '{"app": "npx ts-node bin/app.ts"}\n',
    }
    evidence = service.collect(
        repository_id="repo:cloud-native",
        relative_paths=paths,
        file_texts=texts,
    )
    assert evidence.status is RepositoryCloudParseStatus.SUCCEEDED
    assert evidence.schema_version == REPOSITORY_CLOUD_EVIDENCE_SCHEMA_VERSION
    assert any(item.kind is CloudContainerKind.DOCKER for item in evidence.container_facts)
    assert any(item.kind is CloudContainerKind.DOCKER_COMPOSE for item in evidence.container_facts)
    assert any(item.kind is CloudIaCKind.TERRAFORM for item in evidence.iac_facts)
    assert any(item.kind is CloudIaCKind.BICEP for item in evidence.iac_facts)
    assert any(item.kind is CloudIaCKind.PULUMI for item in evidence.iac_facts)
    assert any(item.kind is CloudIaCKind.CDK for item in evidence.iac_facts)
    assert any(
        item.kind is CloudOrchestrationKind.KUBERNETES for item in evidence.orchestration_facts
    )
    assert any(item.kind is CloudOrchestrationKind.HELM for item in evidence.orchestration_facts)
    assert any(item.platform is CloudPlatformKind.AWS for item in evidence.platform_facts)
    assert any(item.platform is CloudPlatformKind.AZURE for item in evidence.platform_facts)
    assert any(
        item.service is CloudManagedServiceKind.S3 for item in evidence.managed_service_facts
    )
    assert any(
        item.service is CloudManagedServiceKind.DYNAMODB for item in evidence.managed_service_facts
    )
    assert any(
        item.system is CloudDeploymentSystem.GITHUB_ACTIONS for item in evidence.deployment_facts
    )
    payload = repository_cloud_evidence_payload(evidence)
    text = dumps_stable_json(payload)
    assert "Finding" not in text
    assert "severity" not in text.lower()
    assert "readiness_score" not in text
    assert "/Users/" not in text


def test_confirmation_requires_structural_markers() -> None:
    service = RepositoryCloudEvidenceService(RepositoryCloudEvidenceSettings(enabled=True))
    evidence = service.collect(
        repository_id="repo:docker",
        relative_paths=("Dockerfile",),
        file_texts={"Dockerfile": 'FROM alpine:3.19\nCMD ["sh"]\n'},
    )
    assert evidence.container_facts
    assert (
        evidence.container_facts[0].confirmation_level
        is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    )
    assert evidence.container_facts[0].line_hints


def test_deterministic_byte_identical(tmp_path: Path) -> None:
    service = RepositoryCloudEvidenceService(RepositoryCloudEvidenceSettings(enabled=True))
    paths = [
        "Dockerfile",
        "terraform/main.tf",
        "k8s/deployment.yaml",
        ".github/workflows/ci.yml",
    ]
    texts = {
        "Dockerfile": "FROM alpine\n",
        "terraform/main.tf": 'provider "google" {}\nresource "google_storage_bucket" "b" {}\n',
        "k8s/deployment.yaml": "apiVersion: v1\nkind: Service\nmetadata:\n  name: api\n",
        ".github/workflows/ci.yml": "jobs:\n  build:\n    steps:\n      - run: echo hi\n",
    }
    shuffled = paths[:]
    random.Random(7).shuffle(shuffled)
    left = service.collect(
        repository_id="repo:det",
        relative_paths=tuple(shuffled),
        file_texts=texts,
    )
    right = service.collect(
        repository_id="repo:det",
        relative_paths=tuple(reversed(paths)),
        file_texts=texts,
    )
    left_text = dumps_stable_json(repository_cloud_evidence_payload(left))
    right_text = dumps_stable_json(repository_cloud_evidence_payload(right))
    assert left_text == right_text
    assert left.evidence_fingerprint == right.evidence_fingerprint

    written = write_repository_cloud_evidence_artifact(left, tmp_path)
    assert written.path.name == REPOSITORY_CLOUD_EVIDENCE_ARTIFACT_FILENAME
    assert written.path.read_text(encoding="utf-8") == left_text
    again = write_repository_cloud_evidence_artifact(right, tmp_path / "b")
    assert again.path.read_text(encoding="utf-8") == left_text


def test_dedupe_technologies() -> None:
    service = RepositoryCloudEvidenceService(RepositoryCloudEvidenceSettings(enabled=True))
    evidence = service.collect(
        repository_id="repo:dedupe",
        relative_paths=("a/Dockerfile", "b/Dockerfile"),
        file_texts={
            "a/Dockerfile": "FROM alpine\n",
            "b/Dockerfile": "FROM alpine\n",
        },
    )
    assert len(evidence.container_facts) == 2
    assert evidence.coverage.technologies_represented.count("docker") == 1
