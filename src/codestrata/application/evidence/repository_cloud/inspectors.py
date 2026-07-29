"""Content inspection for repository-cloud evidence candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass

from codestrata.domain.evidence.repository_cloud.enums import (
    CloudContainerKind,
    CloudDeploymentSystem,
    CloudDiscoveryBasis,
    CloudIaCKind,
    CloudManagedServiceKind,
    CloudOrchestrationKind,
    CloudPlatformKind,
    CloudServerlessKind,
    EvidenceConfirmationLevel,
)

_FROM_RE = re.compile(r"(?im)^\s*FROM\s+\S+")
_COMPOSE_SERVICES_RE = re.compile(r"(?im)^\s*services\s*:")
_APIVERSION_RE = re.compile(r"(?im)^\s*apiVersion\s*:")
_KIND_RE = re.compile(r"(?im)^\s*kind\s*:\s*(\S+)")
_HELM_NAME_RE = re.compile(r"(?im)^\s*name\s*:")
_AWS_TEMPLATE_RE = re.compile(r"(?im)AWSTemplateFormatVersion")
_SERVERLESS_TRANSFORM_RE = re.compile(r"(?im)AWS::Serverless")
_PULUMI_RUNTIME_RE = re.compile(r"(?im)^\s*runtime\s*:")
_TF_PROVIDER_RE = re.compile(r'(?im)provider\s+"(aws|azurerm|azure|google|google-beta)"')
_TF_RESOURCE_RE = re.compile(r'(?im)resource\s+"([a-z0-9_]+)"')
_CDK_APP_RE = re.compile(r'(?im)"app"\s*:')
_AWS_CDK_LIB_RE = re.compile(r"(?im)aws-cdk-lib|@aws-cdk/")
_BICEP_SCOPE_RE = re.compile(r"(?im)targetScope\s*=")
_ARM_MICROSOFT_RE = re.compile(r"(?im)Microsoft\.[A-Za-z]+/")
_SERVERLESS_PROVIDER_RE = re.compile(r"(?im)^\s*provider\s*:")
_SERVERLESS_FUNCTIONS_RE = re.compile(r"(?im)^\s*functions\s*:")
_OPENSHIFT_KIND_RE = re.compile(
    r"(?im)^\s*kind\s*:\s*(Route|DeploymentConfig|BuildConfig|ImageStream)\b"
)
_OPENSHIFT_API_RE = re.compile(r"(?im)openshift\.io/")
_ARGO_APP_RE = re.compile(r"(?im)^\s*kind\s*:\s*Application\b")
_FLUX_API_RE = re.compile(r"(?im)fluxcd\.io/")
_DEPLOY_STEP_RE = re.compile(
    r"(?im)\b(kubectl|helm|terraform|aws\s+deploy|az\s+deployment|"
    r"gcloud\s+run|docker\s+push|serverless\s+deploy)\b"
)

_MANAGED_SERVICE_PATTERNS: tuple[tuple[CloudManagedServiceKind, re.Pattern[str]], ...] = (
    (
        CloudManagedServiceKind.S3,
        re.compile(r"(?im)\b(aws_s3_bucket|AWS::S3::Bucket|s3\.amazonaws\.com)\b"),
    ),
    (
        CloudManagedServiceKind.DYNAMODB,
        re.compile(r"(?im)\b(aws_dynamodb_table|AWS::DynamoDB::Table|dynamodb)\b"),
    ),
    (
        CloudManagedServiceKind.RDS,
        re.compile(r"(?im)\b(aws_db_instance|aws_rds_|AWS::RDS::)\b"),
    ),
    (CloudManagedServiceKind.SQS, re.compile(r"(?im)\b(aws_sqs_|AWS::SQS::)\b")),
    (CloudManagedServiceKind.SNS, re.compile(r"(?im)\b(aws_sns_|AWS::SNS::)\b")),
    (
        CloudManagedServiceKind.EVENTBRIDGE,
        re.compile(r"(?im)\b(aws_cloudwatch_event_|AWS::Events::|eventbridge)\b"),
    ),
    (
        CloudManagedServiceKind.AZURE_STORAGE,
        re.compile(r"(?im)\b(azurerm_storage_|Microsoft\.Storage/)\b"),
    ),
    (
        CloudManagedServiceKind.AZURE_SERVICE_BUS,
        re.compile(r"(?im)\b(azurerm_servicebus_|Microsoft\.ServiceBus/)\b"),
    ),
    (
        CloudManagedServiceKind.COSMOS_DB,
        re.compile(r"(?im)\b(azurerm_cosmosdb_|Microsoft\.DocumentDB/)\b"),
    ),
    (
        CloudManagedServiceKind.GCS,
        re.compile(r"(?im)\b(google_storage_bucket|storage\.googleapis\.com)\b"),
    ),
    (
        CloudManagedServiceKind.PUBSUB,
        re.compile(r"(?im)\b(google_pubsub_|pubsub\.googleapis\.com)\b"),
    ),
    (
        CloudManagedServiceKind.CLOUD_SQL,
        re.compile(r"(?im)\b(google_sql_|sqladmin\.googleapis\.com)\b"),
    ),
)

_PLATFORM_FROM_PROVIDER = {
    "aws": CloudPlatformKind.AWS,
    "azurerm": CloudPlatformKind.AZURE,
    "azure": CloudPlatformKind.AZURE,
    "google": CloudPlatformKind.GCP,
    "google-beta": CloudPlatformKind.GCP,
}


@dataclass(frozen=True, slots=True)
class ContentHit:
    confirmation_level: EvidenceConfirmationLevel
    discovery_bases: tuple[CloudDiscoveryBasis, ...]
    detail: str | None
    line_hints: tuple[int, ...]
    platforms: tuple[CloudPlatformKind, ...] = ()
    container_kind: CloudContainerKind | None = None
    orchestration_kind: CloudOrchestrationKind | None = None
    iac_kind: CloudIaCKind | None = None
    serverless_kind: CloudServerlessKind | None = None
    deployment_system: CloudDeploymentSystem | None = None
    managed_services: tuple[tuple[CloudManagedServiceKind, str, tuple[int, ...]], ...] = ()


def _line_numbers(text: str, pattern: re.Pattern[str], *, limit: int = 5) -> tuple[int, ...]:
    lines: list[int] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            lines.append(index)
            if len(lines) >= limit:
                break
    return tuple(lines)


def inspect_container_text(text: str, *, kind: CloudContainerKind | None) -> ContentHit | None:
    if kind in {CloudContainerKind.DOCKER, CloudContainerKind.CONTAINERFILE}:
        if _FROM_RE.search(text):
            return ContentHit(
                confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
                discovery_bases=(CloudDiscoveryBasis.CONTENT_MARKER,),
                detail="dockerfile_from_instruction",
                line_hints=_line_numbers(text, _FROM_RE),
                container_kind=kind,
            )
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="dockerfile_without_from",
            line_hints=(),
            container_kind=kind,
        )
    if kind == CloudContainerKind.DOCKER_COMPOSE:
        if _COMPOSE_SERVICES_RE.search(text):
            return ContentHit(
                confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
                discovery_bases=(CloudDiscoveryBasis.STRUCTURED_CONTENT,),
                detail="compose_services_block",
                line_hints=_line_numbers(text, _COMPOSE_SERVICES_RE),
                container_kind=kind,
            )
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            discovery_bases=(),
            detail="compose_without_services",
            line_hints=(),
            container_kind=kind,
        )
    if kind == CloudContainerKind.PODMAN:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            detail="podman_compose_file",
            line_hints=(),
            container_kind=kind,
        )
    if kind == CloudContainerKind.DEVCONTAINER:
        return ContentHit(
            confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
            discovery_bases=(CloudDiscoveryBasis.EXACT_FILENAME,),
            detail="devcontainer_config",
            line_hints=(),
            container_kind=kind,
        )
    return None


def inspect_orchestration_text(
    text: str, *, kind: CloudOrchestrationKind | None
) -> ContentHit | None:
    platforms: list[CloudPlatformKind] = []
    orch = kind
    bases: list[CloudDiscoveryBasis] = []
    detail = None
    lines: list[int] = []
    level = EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED

    if _OPENSHIFT_KIND_RE.search(text) or _OPENSHIFT_API_RE.search(text):
        orch = CloudOrchestrationKind.OPENSHIFT
        bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
        detail = "openshift_manifest"
        lines.extend(_line_numbers(text, _OPENSHIFT_KIND_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    elif kind == CloudOrchestrationKind.HELM and (
        _HELM_NAME_RE.search(text) or _APIVERSION_RE.search(text)
    ):
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "helm_chart_metadata"
        lines.extend(_line_numbers(text, _APIVERSION_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    elif _APIVERSION_RE.search(text) and _KIND_RE.search(text):
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "kubernetes_manifest"
        lines.extend(_line_numbers(text, _KIND_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        if orch is None:
            orch = CloudOrchestrationKind.KUBERNETES

    return ContentHit(
        confirmation_level=level,
        discovery_bases=tuple(bases),
        detail=detail,
        line_hints=tuple(sorted(set(lines)))[:5],
        platforms=tuple(platforms),
        orchestration_kind=orch,
    )


def inspect_iac_text(text: str, *, kind: CloudIaCKind | None) -> ContentHit | None:
    platforms: list[CloudPlatformKind] = []
    bases: list[CloudDiscoveryBasis] = []
    detail = None
    lines: list[int] = []
    level = EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
    iac = kind

    for match in _TF_PROVIDER_RE.finditer(text):
        provider = match.group(1).lower()
        platform = _PLATFORM_FROM_PROVIDER.get(provider)
        if platform is not None and platform not in platforms:
            platforms.append(platform)
        bases.append(CloudDiscoveryBasis.PROVIDER_BLOCK)
        detail = f"terraform_provider:{provider}"
        lines.append(text[: match.start()].count("\n") + 1)
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        iac = CloudIaCKind.TERRAFORM

    if _AWS_TEMPLATE_RE.search(text):
        iac = CloudIaCKind.CLOUDFORMATION
        platforms.append(CloudPlatformKind.AWS)
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "cloudformation_template"
        lines.extend(_line_numbers(text, _AWS_TEMPLATE_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    if _SERVERLESS_TRANSFORM_RE.search(text):
        # SAM templates are also CFN-shaped.
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "aws_sam_transform"
        lines.extend(_line_numbers(text, _SERVERLESS_TRANSFORM_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        platforms.append(CloudPlatformKind.AWS)

    if kind == CloudIaCKind.CDK and (_CDK_APP_RE.search(text) or _AWS_CDK_LIB_RE.search(text)):
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "cdk_app_config"
        lines.extend(_line_numbers(text, _CDK_APP_RE) or _line_numbers(text, _AWS_CDK_LIB_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        platforms.append(CloudPlatformKind.AWS)

    if kind == CloudIaCKind.PULUMI and _PULUMI_RUNTIME_RE.search(text):
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "pulumi_project"
        lines.extend(_line_numbers(text, _PULUMI_RUNTIME_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    if kind == CloudIaCKind.BICEP and _BICEP_SCOPE_RE.search(text):
        bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
        detail = "bicep_target_scope"
        lines.extend(_line_numbers(text, _BICEP_SCOPE_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        platforms.append(CloudPlatformKind.AZURE)

    if kind == CloudIaCKind.ARM and _ARM_MICROSOFT_RE.search(text):
        bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
        detail = "arm_microsoft_resource"
        lines.extend(_line_numbers(text, _ARM_MICROSOFT_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        platforms.append(CloudPlatformKind.AZURE)

    if kind == CloudIaCKind.TERRAFORM and _TF_RESOURCE_RE.search(text) and not bases:
        bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
        detail = "terraform_resource_block"
        lines.extend(_line_numbers(text, _TF_RESOURCE_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    return ContentHit(
        confirmation_level=level,
        discovery_bases=tuple(dict.fromkeys(bases)),
        detail=detail,
        line_hints=tuple(sorted(set(lines)))[:5],
        platforms=tuple(dict.fromkeys(platforms)),
        iac_kind=iac,
    )


def inspect_serverless_text(text: str, *, kind: CloudServerlessKind | None) -> ContentHit | None:
    platforms: list[CloudPlatformKind] = []
    bases: list[CloudDiscoveryBasis] = []
    detail = None
    lines: list[int] = []
    level = EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
    serverless = kind

    if _SERVERLESS_TRANSFORM_RE.search(text):
        serverless = CloudServerlessKind.AWS_SAM
        platforms.append(CloudPlatformKind.AWS)
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "aws_sam_template"
        lines.extend(_line_numbers(text, _SERVERLESS_TRANSFORM_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    elif kind == CloudServerlessKind.SERVERLESS_FRAMEWORK and (
        _SERVERLESS_PROVIDER_RE.search(text) or _SERVERLESS_FUNCTIONS_RE.search(text)
    ):
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "serverless_framework_config"
        lines.extend(_line_numbers(text, _SERVERLESS_PROVIDER_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        if re.search(r"(?im)provider\s*:\s*\n\s*name\s*:\s*aws\b", text) or re.search(
            r"(?im)\bname\s*:\s*aws\b", text
        ):
            platforms.append(CloudPlatformKind.AWS)
    elif kind == CloudServerlessKind.AZURE_FUNCTIONS:
        bases.append(CloudDiscoveryBasis.EXACT_FILENAME)
        detail = "azure_functions_config"
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        platforms.append(CloudPlatformKind.AZURE)
    elif kind == CloudServerlessKind.AWS_SAM and _AWS_TEMPLATE_RE.search(text):
        bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
        detail = "sam_or_cfn_template"
        lines.extend(_line_numbers(text, _AWS_TEMPLATE_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
        platforms.append(CloudPlatformKind.AWS)

    if re.search(r"(?im)cloudfunctions\.googleapis\.com|google\.cloud\.functions", text):
        serverless = CloudServerlessKind.GOOGLE_CLOUD_FUNCTIONS
        platforms.append(CloudPlatformKind.GCP)
        bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
        detail = "google_cloud_functions"
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    if re.search(r"(?im)\b(aws_lambda_|AWS::Lambda::Function)\b", text):
        serverless = CloudServerlessKind.AWS_LAMBDA
        platforms.append(CloudPlatformKind.AWS)
        bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
        detail = "aws_lambda_resource"
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    return ContentHit(
        confirmation_level=level,
        discovery_bases=tuple(dict.fromkeys(bases)),
        detail=detail,
        line_hints=tuple(sorted(set(lines)))[:5],
        platforms=tuple(dict.fromkeys(platforms)),
        serverless_kind=serverless,
    )


def inspect_deployment_text(
    text: str, *, system: CloudDeploymentSystem | None
) -> ContentHit | None:
    bases: list[CloudDiscoveryBasis] = [CloudDiscoveryBasis.CI_WORKFLOW]
    detail = "deployment_workflow_candidate"
    lines: list[int] = []
    level = EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
    deploy = system
    platforms: list[CloudPlatformKind] = []

    if _DEPLOY_STEP_RE.search(text):
        bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
        detail = "cloud_deployment_step"
        lines.extend(_line_numbers(text, _DEPLOY_STEP_RE))
        level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    if system == CloudDeploymentSystem.ARGOCD or _ARGO_APP_RE.search(text):
        deploy = CloudDeploymentSystem.ARGOCD
        if _ARGO_APP_RE.search(text):
            bases.append(CloudDiscoveryBasis.STRUCTURED_CONTENT)
            detail = "argocd_application"
            lines.extend(_line_numbers(text, _ARGO_APP_RE))
            level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    if system == CloudDeploymentSystem.FLUX or _FLUX_API_RE.search(text):
        deploy = CloudDeploymentSystem.FLUX
        if _FLUX_API_RE.search(text):
            bases.append(CloudDiscoveryBasis.CONTENT_MARKER)
            detail = "flux_api_group"
            lines.extend(_line_numbers(text, _FLUX_API_RE))
            level = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED

    if re.search(r"(?im)\b(aws-actions/|amazon/aws-cli|eksctl)\b", text):
        platforms.append(CloudPlatformKind.AWS)
    if re.search(r"(?im)\b(azure/login|azurerm|aks)\b", text):
        platforms.append(CloudPlatformKind.AZURE)
    if re.search(r"(?im)\b(google-github-actions/|gcloud|gke)\b", text):
        platforms.append(CloudPlatformKind.GCP)

    return ContentHit(
        confirmation_level=level,
        discovery_bases=tuple(dict.fromkeys(bases)),
        detail=detail,
        line_hints=tuple(sorted(set(lines)))[:5],
        platforms=tuple(dict.fromkeys(platforms)),
        deployment_system=deploy,
    )


def detect_managed_services(
    text: str,
) -> tuple[tuple[CloudManagedServiceKind, str, tuple[int, ...]], ...]:
    hits: list[tuple[CloudManagedServiceKind, str, tuple[int, ...]]] = []
    seen: set[CloudManagedServiceKind] = set()
    for service, pattern in _MANAGED_SERVICE_PATTERNS:
        if service in seen:
            continue
        if pattern.search(text):
            seen.add(service)
            hits.append((service, pattern.pattern, _line_numbers(text, pattern)))
    return tuple(sorted(hits, key=lambda item: item[0].value))
