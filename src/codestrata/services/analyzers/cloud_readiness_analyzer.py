"""Detect container, infrastructure, and cloud deployment assets."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.models import (
    AnalyzerResult,
    CicdFacts,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
)
from codestrata.models.normalized_facts import CloudReadinessFacts


class CloudReadinessAnalyzer:
    """Detect deterministic cloud and deployment readiness signals."""

    _DOCKER_FILE_NAMES = {
        "dockerfile",
        "dockerfile.dev",
        "dockerfile.prod",
        "dockerfile.production",
    }

    _DOCKER_COMPOSE_FILES = {
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    }

    _KUBERNETES_DIRECTORIES = {
        "k8s",
        "kubernetes",
        "manifests",
    }

    _KUBERNETES_FILE_MARKERS = {
        "deployment",
        "service",
        "ingress",
        "statefulset",
        "daemonset",
        "configmap",
        "secret",
        "namespace",
    }

    _TERRAFORM_SUFFIXES = {
        ".tf",
        ".tfvars",
    }

    _CLOUDFORMATION_MARKERS = {
        "cloudformation",
        "cfn",
    }

    _SERVERLESS_FILES = {
        "serverless.yml",
        "serverless.yaml",
        "samconfig.toml",
        "template.yml",
        "template.yaml",
    }

    _HELM_FILE_NAMES = {
        "chart.yaml",
        "values.yaml",
        "values.yml",
    }

    _DEPLOYMENT_WORKFLOW_MARKERS = {
        "deploy",
        "deployment",
        "release",
        "publish",
        "production",
        "staging",
    }

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Analyze repository files for cloud readiness signals."""

        del technologies
        del facts

        detected: dict[str, list[str]] = {
            "docker": [],
            "devcontainer": [],
            "docker_compose": [],
            "kubernetes": [],
            "terraform": [],
            "cloudformation": [],
            "serverless": [],
            "helm": [],
            "deployment_workflows": [],
        }

        for relative_path in repository.files:
            normalized_path = relative_path.replace("\\", "/")
            lowered_path = normalized_path.lower()
            path = PurePosixPath(lowered_path)
            file_name = path.name
            path_parts = set(path.parts)

            if self._is_dockerfile(file_name):
                if self._is_devcontainer_path(path):
                    detected["devcontainer"].append(normalized_path)
                else:
                    detected["docker"].append(normalized_path)

            if file_name in self._DOCKER_COMPOSE_FILES:
                detected["docker_compose"].append(normalized_path)

            if self._is_kubernetes_file(
                path_parts=path_parts,
                file_name=file_name,
                suffix=path.suffix,
            ):
                detected["kubernetes"].append(normalized_path)

            if path.suffix in self._TERRAFORM_SUFFIXES:
                detected["terraform"].append(normalized_path)

            if self._is_cloudformation_file(
                lowered_path=lowered_path,
                file_name=file_name,
            ):
                detected["cloudformation"].append(normalized_path)

            if file_name in self._SERVERLESS_FILES:
                detected["serverless"].append(normalized_path)

            if self._is_helm_file(
                path_parts=path_parts,
                file_name=file_name,
            ):
                detected["helm"].append(normalized_path)

            if self._is_deployment_workflow(
                lowered_path=lowered_path,
                file_name=file_name,
            ):
                detected["deployment_workflows"].append(normalized_path)

        findings: list[Finding] = []

        findings.extend(self._container_findings(detected))
        findings.extend(self._orchestration_findings(detected))
        findings.extend(self._infrastructure_findings(detected))
        findings.extend(self._deployment_findings(detected))
        findings.extend(self._readiness_summary(detected))

        has_docker = bool(detected["docker"])
        has_devcontainer = bool(detected["devcontainer"])
        has_docker_compose = bool(detected["docker_compose"])
        has_kubernetes = bool(detected["kubernetes"])
        has_helm = bool(detected["helm"])
        has_terraform = bool(detected["terraform"])
        has_cloudformation = bool(detected["cloudformation"])
        has_serverless = bool(detected["serverless"])
        has_deployment_workflow = bool(detected["deployment_workflows"])

        cloud_capabilities = [
            capability
            for capability, present in (
                ("docker", has_docker),
                ("devcontainer", has_devcontainer),
                ("docker-compose", has_docker_compose),
                ("kubernetes", has_kubernetes),
                ("helm", has_helm),
                ("terraform", has_terraform),
                ("cloudformation", has_cloudformation),
                ("serverless", has_serverless),
                ("deployment-workflow", has_deployment_workflow),
            )
            if present
        ]

        return AnalyzerResult(
            findings=findings,
            facts=RepositoryFacts(
                cloud=CloudReadinessFacts(
                    has_docker=has_docker,
                    has_devcontainer=has_devcontainer,
                    has_docker_compose=has_docker_compose,
                    has_kubernetes=has_kubernetes,
                    has_helm=has_helm,
                    has_terraform=has_terraform,
                    has_cloudformation=has_cloudformation,
                    has_serverless=has_serverless,
                    cloud_capabilities=cloud_capabilities,
                ),
                cicd=CicdFacts(
                    has_deployment_workflow=has_deployment_workflow,
                ),
            ),
        )

    def _container_findings(
        self,
        detected: dict[str, list[str]],
    ) -> list[Finding]:
        """Create container-related findings."""

        findings: list[Finding] = []

        if detected["docker"]:
            findings.append(
                self._finding(
                    rule_id="CLOUD001",
                    title="Docker containerization detected",
                    severity=Severity.INFO,
                    evidence=(f"Detected {len(detected['docker'])} Dockerfile configuration(s)"),
                    metadata={
                        "file_count": len(detected["docker"]),
                        "sample_paths": detected["docker"][:10],
                    },
                )
            )

        if detected["docker_compose"]:
            findings.append(
                self._finding(
                    rule_id="CLOUD002",
                    title="Docker Compose environment detected",
                    severity=Severity.INFO,
                    evidence=(
                        f"Detected {len(detected['docker_compose'])} "
                        "Docker Compose configuration(s)"
                    ),
                    metadata={
                        "file_count": len(detected["docker_compose"]),
                        "sample_paths": (detected["docker_compose"][:10]),
                    },
                )
            )

        return findings

    def _orchestration_findings(
        self,
        detected: dict[str, list[str]],
    ) -> list[Finding]:
        """Create Kubernetes and Helm findings."""

        findings: list[Finding] = []

        if detected["kubernetes"]:
            findings.append(
                self._finding(
                    rule_id="CLOUD003",
                    title="Kubernetes deployment assets detected",
                    severity=Severity.INFO,
                    evidence=(f"Detected {len(detected['kubernetes'])} Kubernetes-related file(s)"),
                    metadata={
                        "file_count": len(detected["kubernetes"]),
                        "sample_paths": (detected["kubernetes"][:10]),
                    },
                )
            )

        if detected["helm"]:
            findings.append(
                self._finding(
                    rule_id="CLOUD004",
                    title="Helm packaging detected",
                    severity=Severity.INFO,
                    evidence=(f"Detected {len(detected['helm'])} Helm chart file(s)"),
                    metadata={
                        "file_count": len(detected["helm"]),
                        "sample_paths": detected["helm"][:10],
                    },
                )
            )

        return findings

    def _infrastructure_findings(
        self,
        detected: dict[str, list[str]],
    ) -> list[Finding]:
        """Create infrastructure-as-code findings."""

        findings: list[Finding] = []

        if detected["terraform"]:
            findings.append(
                self._finding(
                    rule_id="CLOUD005",
                    title="Terraform infrastructure detected",
                    severity=Severity.INFO,
                    evidence=(f"Detected {len(detected['terraform'])} Terraform file(s)"),
                    metadata={
                        "tool": "terraform",
                        "file_count": len(detected["terraform"]),
                        "sample_paths": (detected["terraform"][:10]),
                    },
                )
            )

        if detected["cloudformation"]:
            findings.append(
                self._finding(
                    rule_id="CLOUD006",
                    title="AWS CloudFormation assets detected",
                    severity=Severity.INFO,
                    evidence=(
                        f"Detected {len(detected['cloudformation'])} CloudFormation-related file(s)"
                    ),
                    metadata={
                        "tool": "cloudformation",
                        "file_count": len(detected["cloudformation"]),
                        "sample_paths": (detected["cloudformation"][:10]),
                    },
                )
            )

        if detected["serverless"]:
            findings.append(
                self._finding(
                    rule_id="CLOUD007",
                    title="Serverless deployment assets detected",
                    severity=Severity.INFO,
                    evidence=(
                        f"Detected {len(detected['serverless'])} serverless deployment file(s)"
                    ),
                    metadata={
                        "file_count": len(detected["serverless"]),
                        "sample_paths": (detected["serverless"][:10]),
                    },
                )
            )

        return findings

    def _deployment_findings(
        self,
        detected: dict[str, list[str]],
    ) -> list[Finding]:
        """Create CI/CD deployment findings."""

        deployment_workflows = detected["deployment_workflows"]

        if not deployment_workflows:
            return []

        return [
            self._finding(
                rule_id="CLOUD008",
                title="Automated deployment workflow detected",
                severity=Severity.INFO,
                evidence=(
                    f"Detected {len(deployment_workflows)} deployment-oriented workflow file(s)"
                ),
                metadata={
                    "file_count": len(deployment_workflows),
                    "sample_paths": deployment_workflows[:10],
                },
            )
        ]

    def _readiness_summary(
        self,
        detected: dict[str, list[str]],
    ) -> list[Finding]:
        """Create a high-level cloud readiness summary."""

        capabilities = [capability for capability, paths in detected.items() if paths]

        if not capabilities:
            return [
                self._finding(
                    rule_id="CLOUD009",
                    title="No cloud deployment assets detected",
                    severity=Severity.LOW,
                    evidence=(
                        "No container, orchestration, "
                        "infrastructure-as-code, or deployment "
                        "workflow files were detected"
                    ),
                    metadata={
                        "capabilities": [],
                    },
                )
            ]

        return [
            self._finding(
                rule_id="CLOUD010",
                title="Cloud deployment readiness signals detected",
                severity=Severity.INFO,
                evidence=("Detected cloud capabilities: " + ", ".join(sorted(capabilities))),
                metadata={
                    "capabilities": sorted(capabilities),
                    "capability_count": len(capabilities),
                },
            )
        ]

    def _is_dockerfile(
        self,
        file_name: str,
    ) -> bool:
        """Return whether the file is a Dockerfile."""

        return file_name in self._DOCKER_FILE_NAMES or file_name.startswith("dockerfile.")

    def _is_devcontainer_path(
        self,
        path: PurePosixPath,
    ) -> bool:
        """Return whether a Dockerfile belongs to a development container."""

        return ".devcontainer" in path.parts

    def _is_kubernetes_file(
        self,
        path_parts: set[str],
        file_name: str,
        suffix: str,
    ) -> bool:
        """Return whether the path appears to be Kubernetes configuration."""

        if suffix not in {".yml", ".yaml"}:
            return False

        if path_parts & self._KUBERNETES_DIRECTORIES:
            return True

        file_stem = file_name.removesuffix(suffix)

        return any(marker in file_stem for marker in self._KUBERNETES_FILE_MARKERS)

    def _is_cloudformation_file(
        self,
        lowered_path: str,
        file_name: str,
    ) -> bool:
        """Return whether the file appears to be CloudFormation."""

        if not file_name.endswith((".yml", ".yaml", ".json")):
            return False

        return any(marker in lowered_path for marker in self._CLOUDFORMATION_MARKERS)

    def _is_helm_file(
        self,
        path_parts: set[str],
        file_name: str,
    ) -> bool:
        """Return whether the file belongs to a Helm chart."""

        if "helm" in path_parts or "charts" in path_parts:
            return file_name.endswith((".yml", ".yaml"))

        return file_name in self._HELM_FILE_NAMES

    def _is_deployment_workflow(
        self,
        lowered_path: str,
        file_name: str,
    ) -> bool:
        """Return whether a CI workflow name suggests deployment."""

        if not lowered_path.startswith(".github/workflows/"):
            return False

        if not file_name.endswith((".yml", ".yaml")):
            return False

        return any(marker in file_name for marker in self._DEPLOYMENT_WORKFLOW_MARKERS)

    def _finding(
        self,
        rule_id: str,
        title: str,
        severity: Severity,
        evidence: str,
        metadata: dict[str, object],
    ) -> Finding:
        """Create a cloud-readiness finding."""

        sample_paths = metadata.get("sample_paths")
        file_path = "."

        if isinstance(sample_paths, list) and sample_paths:
            first_path = sample_paths[0]
            if isinstance(first_path, str):
                file_path = first_path
        else:
            path_value = metadata.get("path")
            if isinstance(path_value, str):
                file_path = path_value

        return Finding(
            rule_id=rule_id,
            title=title,
            description=evidence,
            category=FindingCategory.CLOUD_READINESS,
            severity=severity,
            source=FindingSource.STATIC_ANALYSIS,
            evidence=[
                Evidence(
                    file_path=file_path,
                    description=evidence,
                )
            ],
            affected_technologies=[],
            metadata=metadata,
        )
