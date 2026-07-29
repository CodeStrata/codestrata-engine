"""Cloud Intelligence pack identifiers (Phase 4.7.3).

``cloud.core`` hygiene rules consume AggregatedRepositoryCloudEvidence only.
Human aliases: CLOUD-001 … CLOUD-061 map to ``cloud.cloud-00N`` rule IDs
(Shared Rule Platform namespace.kebab form).
"""

from __future__ import annotations

PACK_ID = "cloud.core"
PACK_VERSION = "1.0.0"
PACK_TITLE = "Cloud Intelligence Core"
PACK_DESCRIPTION = (
    "Cloud Intelligence SharedRule pack for repository-observable cloud "
    "technology and deployment signals. Rules consume "
    "AggregatedRepositoryCloudEvidence only and never re-read repository "
    "files, call cloud provider APIs, or produce readiness scores."
)

RULE_ID_PREFIX = "cloud."
RULE_VERSION = "1.0.0"

TAXONOMY_NAMESPACE = "cloud"

# Machine IDs (platform-valid). Documented aliases: CLOUD-001 … CLOUD-061.
RULE_MULTIPLE_PLATFORMS = "cloud.cloud-001"
RULE_PLATFORM_DETECTED = "cloud.cloud-002"
RULE_CONTAINERIZATION = "cloud.cloud-010"
RULE_KUBERNETES = "cloud.cloud-011"
RULE_IAC_PRESENT = "cloud.cloud-020"
RULE_MULTIPLE_IAC = "cloud.cloud-021"
RULE_SERVERLESS = "cloud.cloud-030"
RULE_DEPLOYMENT_PIPELINE = "cloud.cloud-040"
RULE_MANAGED_SERVICES = "cloud.cloud-050"
RULE_CLOUD_NATIVE_INDICATORS = "cloud.cloud-060"
RULE_DEPLOYMENT_WITHOUT_PLATFORM = "cloud.cloud-061"

HYGIENE_RULE_IDS: tuple[str, ...] = (
    RULE_MULTIPLE_PLATFORMS,
    RULE_PLATFORM_DETECTED,
    RULE_CONTAINERIZATION,
    RULE_KUBERNETES,
    RULE_IAC_PRESENT,
    RULE_MULTIPLE_IAC,
    RULE_SERVERLESS,
    RULE_DEPLOYMENT_PIPELINE,
    RULE_MANAGED_SERVICES,
    RULE_CLOUD_NATIVE_INDICATORS,
    RULE_DEPLOYMENT_WITHOUT_PLATFORM,
)

CLOUD_RULE_IDS: tuple[str, ...] = HYGIENE_RULE_IDS

DEFERRED_RULE_IDS: tuple[str, ...] = ()

RULE_ALIAS_TO_ID: dict[str, str] = {
    "CLOUD-001": RULE_MULTIPLE_PLATFORMS,
    "CLOUD-002": RULE_PLATFORM_DETECTED,
    "CLOUD-010": RULE_CONTAINERIZATION,
    "CLOUD-011": RULE_KUBERNETES,
    "CLOUD-020": RULE_IAC_PRESENT,
    "CLOUD-021": RULE_MULTIPLE_IAC,
    "CLOUD-030": RULE_SERVERLESS,
    "CLOUD-040": RULE_DEPLOYMENT_PIPELINE,
    "CLOUD-050": RULE_MANAGED_SERVICES,
    "CLOUD-060": RULE_CLOUD_NATIVE_INDICATORS,
    "CLOUD-061": RULE_DEPLOYMENT_WITHOUT_PLATFORM,
}
