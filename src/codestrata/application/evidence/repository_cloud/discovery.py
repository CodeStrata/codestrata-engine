"""Candidate path discovery for repository-cloud evidence."""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from codestrata.domain.evidence.repository_cloud.enums import (
    CloudContainerKind,
    CloudDeploymentSystem,
    CloudDiscoveryBasis,
    CloudEvidenceFamily,
    CloudIaCKind,
    CloudOrchestrationKind,
    CloudServerlessKind,
)
from codestrata.scan_boundary import default_ignore_path_markers

DEFAULT_IGNORE_MARKERS: tuple[str, ...] = default_ignore_path_markers()

_K8S_DIR_MARKERS = frozenset({"k8s", "kubernetes", "manifests", "kube", "deployments"})
_HELM_DIR_MARKERS = frozenset({"charts", "helm", "chart"})
_TF_DIR_MARKERS = frozenset({"terraform", "tf"})
_CFN_DIR_MARKERS = frozenset({"cloudformation", "cfn", "cf-templates"})
_ARGO_DIR_MARKERS = frozenset({"argocd", "argo-cd", "argo"})
_FLUX_DIR_MARKERS = frozenset({"flux", "fluxcd", "flux-system"})

_K8S_KIND_NAMES = frozenset(
    {
        "deployment",
        "service",
        "ingress",
        "statefulset",
        "daemonset",
        "configmap",
        "secret",
        "namespace",
        "job",
        "cronjob",
        "persistentvolumeclaim",
        "persistentvolume",
        "role",
        "rolebinding",
        "serviceaccount",
        "networkpolicy",
        "horizontalpodautoscaler",
    }
)


@dataclass(frozen=True, slots=True)
class CloudPathClassification:
    path: str
    family: CloudEvidenceFamily
    discovery_bases: tuple[CloudDiscoveryBasis, ...]
    technology_hints: tuple[str, ...]
    container_kind: CloudContainerKind | None = None
    orchestration_kind: CloudOrchestrationKind | None = None
    iac_kind: CloudIaCKind | None = None
    serverless_kind: CloudServerlessKind | None = None
    deployment_system: CloudDeploymentSystem | None = None


def normalize_relative_path(path: str) -> str:
    text = path.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def is_ignored_path(path: str, *, ignore_markers: Sequence[str]) -> bool:
    normalized = f"/{normalize_relative_path(path).lower()}/"
    return any(marker.lower() in normalized for marker in ignore_markers)


def _path_parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(normalize_relative_path(path)).parts)


def _yaml_suffix(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(".yml") or lower.endswith(".yaml")


def _classify_container(name: str, parts: Sequence[str]) -> CloudPathClassification | None:
    lower = name.lower()
    if lower == "dockerfile" or lower.startswith("dockerfile."):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.CONTAINER,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("docker",),
            container_kind=CloudContainerKind.DOCKER,
        )
    if lower == "containerfile" or lower.startswith("containerfile."):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.CONTAINER,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("containerfile",),
            container_kind=CloudContainerKind.CONTAINERFILE,
        )
    if lower in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.CONTAINER,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("docker_compose",),
            container_kind=CloudContainerKind.DOCKER_COMPOSE,
        )
    if lower in {"podman-compose.yml", "podman-compose.yaml"}:
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.CONTAINER,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("podman",),
            container_kind=CloudContainerKind.PODMAN,
        )
    if ".devcontainer" in parts and _yaml_suffix(name):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.CONTAINER,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("devcontainer",),
            container_kind=CloudContainerKind.DEVCONTAINER,
        )
    if lower == "devcontainer.json":
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.CONTAINER,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("devcontainer",),
            container_kind=CloudContainerKind.DEVCONTAINER,
        )
    return None


def _classify_iac(
    name: str, parts: Sequence[str], path_lower: str
) -> CloudPathClassification | None:
    lower = name.lower()
    if lower.endswith(".tf") or lower.endswith(".tfvars") or lower == ".terraform.lock.hcl":
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.IAC,
            discovery_bases=(CloudDiscoveryBasis.EXTENSION,),
            technology_hints=("terraform",),
            iac_kind=CloudIaCKind.TERRAFORM,
        )
    if any(part in _TF_DIR_MARKERS for part in parts) and (
        lower.endswith(".hcl") or lower in {"main.tf", "variables.tf", "outputs.tf"}
    ):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.IAC,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("terraform",),
            iac_kind=CloudIaCKind.TERRAFORM,
        )
    if lower == "cdk.json" or lower == "cdk.context.json":
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.IAC,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("cdk",),
            iac_kind=CloudIaCKind.CDK,
        )
    if lower == "pulumi.yaml" or fnmatch.fnmatch(lower, "pulumi.*.yaml"):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.IAC,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("pulumi",),
            iac_kind=CloudIaCKind.PULUMI,
        )
    if lower.endswith(".bicep"):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.IAC,
            discovery_bases=(CloudDiscoveryBasis.EXTENSION,),
            technology_hints=("bicep",),
            iac_kind=CloudIaCKind.BICEP,
        )
    if lower in {"azuredeploy.json", "azuredeploy.parameters.json"} or (
        lower.endswith(".parameters.json") and "azure" in path_lower
    ):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.IAC,
            discovery_bases=(CloudDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("arm",),
            iac_kind=CloudIaCKind.ARM,
        )
    if any(part in _CFN_DIR_MARKERS for part in parts) and (
        _yaml_suffix(name) or lower.endswith(".json") or lower.endswith(".template")
    ):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.IAC,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("cloudformation",),
            iac_kind=CloudIaCKind.CLOUDFORMATION,
        )
    if "cloudformation" in lower or lower.startswith("cfn-") or lower.endswith(".cfn.yml"):
        if _yaml_suffix(name) or lower.endswith(".json") or lower.endswith(".template"):
            return CloudPathClassification(
                path="",
                family=CloudEvidenceFamily.IAC,
                discovery_bases=(CloudDiscoveryBasis.FILENAME_PATTERN,),
                technology_hints=("cloudformation",),
                iac_kind=CloudIaCKind.CLOUDFORMATION,
            )
    return None


def _classify_serverless(name: str) -> CloudPathClassification | None:
    lower = name.lower()
    if lower in {"serverless.yml", "serverless.yaml"}:
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.SERVERLESS,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("serverless_framework",),
            serverless_kind=CloudServerlessKind.SERVERLESS_FRAMEWORK,
        )
    if lower == "samconfig.toml":
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.SERVERLESS,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("aws_sam",),
            serverless_kind=CloudServerlessKind.AWS_SAM,
        )
    if lower in {"template.yml", "template.yaml"}:
        # Candidate only — content inspection confirms SAM/CFN.
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.SERVERLESS,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("aws_sam", "cloudformation"),
            serverless_kind=CloudServerlessKind.AWS_SAM,
        )
    if lower in {"host.json", "function.json", "local.settings.json"}:
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.SERVERLESS,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("azure_functions",),
            serverless_kind=CloudServerlessKind.AZURE_FUNCTIONS,
        )
    return None


def _classify_orchestration(name: str, parts: Sequence[str]) -> CloudPathClassification | None:
    lower = name.lower()
    if lower == "chart.yaml":
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.ORCHESTRATION,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("helm",),
            orchestration_kind=CloudOrchestrationKind.HELM,
        )
    if lower in {"values.yaml", "values.yml"} and any(part in _HELM_DIR_MARKERS for part in parts):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.ORCHESTRATION,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("helm",),
            orchestration_kind=CloudOrchestrationKind.HELM,
        )
    if any(part in _HELM_DIR_MARKERS for part in parts) and _yaml_suffix(name):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.ORCHESTRATION,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("helm",),
            orchestration_kind=CloudOrchestrationKind.HELM,
        )
    if any(part in _K8S_DIR_MARKERS for part in parts) and _yaml_suffix(name):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.ORCHESTRATION,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("kubernetes",),
            orchestration_kind=CloudOrchestrationKind.KUBERNETES,
        )
    stem = PurePosixPath(name).stem.lower()
    # Exact or kind-prefixed names only (deployment.yaml, deployment-api.yaml).
    # Do not match product names like registration-service.yaml.
    if _yaml_suffix(name) and any(
        stem == kind or stem.startswith(f"{kind}-") for kind in _K8S_KIND_NAMES
    ):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.ORCHESTRATION,
            discovery_bases=(CloudDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("kubernetes",),
            orchestration_kind=CloudOrchestrationKind.KUBERNETES,
        )
    return None


def _classify_deployment(
    name: str, parts: Sequence[str], path_lower: str
) -> CloudPathClassification | None:
    lower = name.lower()
    if ".github" in parts and "workflows" in parts and _yaml_suffix(name):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.DEPLOYMENT,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("github_actions",),
            deployment_system=CloudDeploymentSystem.GITHUB_ACTIONS,
        )
    if lower in {".gitlab-ci.yml", ".gitlab-ci.yaml"}:
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.DEPLOYMENT,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("gitlab_ci",),
            deployment_system=CloudDeploymentSystem.GITLAB_CI,
        )
    if lower.startswith("azure-pipelines") and _yaml_suffix(name):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.DEPLOYMENT,
            discovery_bases=(CloudDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("azure_devops",),
            deployment_system=CloudDeploymentSystem.AZURE_DEVOPS,
        )
    if lower == "jenkinsfile" or lower.startswith("jenkinsfile."):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.DEPLOYMENT,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            technology_hints=("jenkins",),
            deployment_system=CloudDeploymentSystem.JENKINS,
        )
    if any(part in _ARGO_DIR_MARKERS for part in parts) and _yaml_suffix(name):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.DEPLOYMENT,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("argocd",),
            deployment_system=CloudDeploymentSystem.ARGOCD,
        )
    if any(part in _FLUX_DIR_MARKERS for part in parts) and _yaml_suffix(name):
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.DEPLOYMENT,
            discovery_bases=(CloudDiscoveryBasis.DIRECTORY_CONVENTION,),
            technology_hints=("flux",),
            deployment_system=CloudDeploymentSystem.FLUX,
        )
    if lower in {"kustomization.yaml", "kustomization.yml"} and "flux" in path_lower:
        return CloudPathClassification(
            path="",
            family=CloudEvidenceFamily.DEPLOYMENT,
            discovery_bases=(CloudDiscoveryBasis.FILENAME_PATTERN,),
            technology_hints=("flux",),
            deployment_system=CloudDeploymentSystem.FLUX,
        )
    return None


def classify_cloud_candidate(path: str) -> CloudPathClassification | None:
    """Classify a relative path as a cloud evidence candidate, or None."""

    normalized = normalize_relative_path(path)
    if not normalized:
        return None
    parts = _path_parts(normalized)
    name = PurePosixPath(normalized).name
    path_lower = normalized.lower()

    for classified in (
        _classify_container(name, parts),
        _classify_iac(name, parts, path_lower),
        _classify_serverless(name),
        _classify_orchestration(name, parts),
        _classify_deployment(name, parts, path_lower),
    ):
        if classified is not None:
            return CloudPathClassification(
                path=normalized,
                family=classified.family,
                discovery_bases=classified.discovery_bases,
                technology_hints=classified.technology_hints,
                container_kind=classified.container_kind,
                orchestration_kind=classified.orchestration_kind,
                iac_kind=classified.iac_kind,
                serverless_kind=classified.serverless_kind,
                deployment_system=classified.deployment_system,
            )
    return None


def discover_cloud_candidates(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> list[CloudPathClassification]:
    found: list[CloudPathClassification] = []
    for raw in relative_paths:
        normalized = normalize_relative_path(raw)
        if not normalized or is_ignored_path(normalized, ignore_markers=ignore_markers):
            continue
        classified = classify_cloud_candidate(normalized)
        if classified is not None:
            found.append(classified)
    found.sort(key=lambda item: item.path)
    return found[:max_files]
