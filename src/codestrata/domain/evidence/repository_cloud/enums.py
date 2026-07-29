"""Repository-cloud evidence enums (Phase 4.7.2).

Technology-neutral taxonomy for repository-observable cloud artifacts.
Not a Cloud Intelligence capability enum and not Findings.
"""

from __future__ import annotations

from enum import StrEnum


class CloudEvidenceFamily(StrEnum):
    PLATFORM = "platform"
    CONTAINER = "container"
    ORCHESTRATION = "orchestration"
    IAC = "iac"
    SERVERLESS = "serverless"
    MANAGED_SERVICE = "managed_service"
    DEPLOYMENT = "deployment"
    UNKNOWN = "unknown"


class CloudPlatformKind(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    UNKNOWN = "unknown"


class CloudContainerKind(StrEnum):
    DOCKER = "docker"
    DOCKER_COMPOSE = "docker_compose"
    PODMAN = "podman"
    DEVCONTAINER = "devcontainer"
    CONTAINERFILE = "containerfile"
    UNKNOWN = "unknown"


class CloudOrchestrationKind(StrEnum):
    KUBERNETES = "kubernetes"
    HELM = "helm"
    OPENSHIFT = "openshift"
    UNKNOWN = "unknown"


class CloudIaCKind(StrEnum):
    TERRAFORM = "terraform"
    CLOUDFORMATION = "cloudformation"
    CDK = "cdk"
    PULUMI = "pulumi"
    ARM = "arm"
    BICEP = "bicep"
    UNKNOWN = "unknown"


class CloudServerlessKind(StrEnum):
    AWS_LAMBDA = "aws_lambda"
    AZURE_FUNCTIONS = "azure_functions"
    GOOGLE_CLOUD_FUNCTIONS = "google_cloud_functions"
    SERVERLESS_FRAMEWORK = "serverless_framework"
    AWS_SAM = "aws_sam"
    UNKNOWN = "unknown"


class CloudManagedServiceKind(StrEnum):
    S3 = "s3"
    DYNAMODB = "dynamodb"
    RDS = "rds"
    SQS = "sqs"
    SNS = "sns"
    EVENTBRIDGE = "eventbridge"
    AZURE_STORAGE = "azure_storage"
    AZURE_SERVICE_BUS = "azure_service_bus"
    COSMOS_DB = "cosmos_db"
    GCS = "gcs"
    PUBSUB = "pubsub"
    CLOUD_SQL = "cloud_sql"
    UNKNOWN = "unknown"


class CloudDeploymentSystem(StrEnum):
    GITHUB_ACTIONS = "github_actions"
    AZURE_DEVOPS = "azure_devops"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    ARGOCD = "argocd"
    FLUX = "flux"
    UNKNOWN = "unknown"


class EvidenceConfirmationLevel(StrEnum):
    DISCOVERED_CANDIDATE = "discovered_candidate"
    STRUCTURALLY_INSPECTED = "structurally_inspected"
    STRUCTURALLY_CONFIRMED = "structurally_confirmed"
    DECLARED = "declared"
    CONFIGURED = "configured"
    UNSUPPORTED = "unsupported"
    MALFORMED = "malformed"
    SKIPPED = "skipped"


class CloudDiscoveryBasis(StrEnum):
    EXACT_FILENAME = "exact_filename"
    FILENAME_PATTERN = "filename_pattern"
    EXTENSION = "extension"
    DIRECTORY_CONVENTION = "directory_convention"
    CONTENT_MARKER = "content_marker"
    STRUCTURED_CONTENT = "structured_content"
    PROVIDER_BLOCK = "provider_block"
    DEPENDENCY_DECLARATION = "dependency_declaration"
    CI_WORKFLOW = "ci_workflow"


class RepositoryCloudParseStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RepositoryCloudLimitationCategory(StrEnum):
    REPOSITORY_SNAPSHOT_ONLY = "repository-snapshot-only"
    NO_CLOUD_RUNTIME = "no-cloud-runtime"
    NO_PROVIDER_API = "no-provider-api"
    NO_DEPLOYMENT_EXECUTION = "no-deployment-execution"
    DETECTION_BOUNDED = "detection-bounded"
    NO_READINESS_SCORE = "no-readiness-score"
    NO_COST_OR_SECURITY_JUDGMENT = "no-cost-or-security-judgment"
    GENERATED_VENDOR_EXCLUSIONS = "generated-vendor-exclusions"
    MANAGED_SERVICE_CONTENT_BOUNDED = "managed-service-content-bounded"
    OTHER = "other"
