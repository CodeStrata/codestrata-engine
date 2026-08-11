"""Anonymous runtime analytics model and local collection (Epic 10 Slice 10.3).

Constructs in-memory runtime analytics only. Does not transmit. Does not persist
analytics payloads. May ensure the Slice 10.2 anonymous installation identity.
"""

from __future__ import annotations

import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codestrata.package_metadata import get_package_version
from codestrata.telemetry.analytics.events import (
    AnalyticsCategory,
    AnalyticsEvent,
    AnalyticsLifecycle,
    _APPROVED_ARCHITECTURES,
    _APPROVED_OS_FAMILIES,
)
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    ensure_anonymous_installation_identity,
    is_uuid_v4,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)

COMMUNITY_RUNTIME_ANALYTICS_POLICY_ID = "community-runtime-analytics-policy"
COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION = "1.0"
COMMUNITY_RUNTIME_ANALYTICS_POLICY_URN = (
    f"{COMMUNITY_RUNTIME_ANALYTICS_POLICY_ID}:"
    f"{COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION}"
)

COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_ID = "community-runtime-analytics-schema"
COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION = "1.0"
COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_URN = (
    f"{COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_ID}:"
    f"{COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION}"
)

RUNTIME_ANALYTICS_EVENT_TYPE = "analytics_runtime_collected"

_REVIEW_STATUS = "local_collection_only_no_transmission_no_analytics_persistence"

_LIMITATIONS: tuple[str, ...] = (
    "runtime_category_only",
    "local_construction_only",
    "no_transmission",
    "no_analytics_persistence",
    "installation_identity_only_identifier",
    "requires_prior_privacy_projection",
    "not_wired_into_cli_product_path",
    "no_telemetry_transport_modification",
    "no_telemetry_consent_modification",
    "community_cloud_deferred",
    "data_lake_deferred",
)

_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+){1,3}([a-zA-Z0-9._+-]{0,16})?$")
_ADOPTION_RE = re.compile(r"^[0-9]+\.[0-9]+$")
_RUNTIME_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")


class RuntimeAnalyticsPolicyError(ValueError):
    """Raised when runtime-analytics policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityRuntimeAnalyticsPolicy:
    """Independent policy for local runtime analytics construction."""

    policy_id: str = COMMUNITY_RUNTIME_ANALYTICS_POLICY_ID
    policy_version: str = COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION
    schema_id: str = COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_ID
    schema_version: str = COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    local_collection_allowed: bool = True
    persistence_enabled: bool = False
    transmission_enabled: bool = False
    installation_id_required: bool = True
    installation_id_only_identifier: bool = True
    requires_prior_privacy_projection: bool = True
    category_runtime_only: bool = True
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    @property
    def schema_token(self) -> str:
        return f"{self.schema_id}:{self.schema_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_RUNTIME_ANALYTICS_POLICY_ID:
            raise RuntimeAnalyticsPolicyError("unsupported runtime analytics policy id")
        if self.policy_version != COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION:
            raise RuntimeAnalyticsPolicyError(
                "unsupported runtime analytics policy version"
            )
        if self.schema_id != COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_ID:
            raise RuntimeAnalyticsPolicyError("unsupported runtime analytics schema id")
        if self.schema_version != COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION:
            raise RuntimeAnalyticsPolicyError(
                "unsupported runtime analytics schema version"
            )
        if self.review_status != _REVIEW_STATUS:
            raise RuntimeAnalyticsPolicyError("unsupported runtime analytics review_status")
        if not self.local_collection_allowed:
            raise RuntimeAnalyticsPolicyError("local_collection_allowed must be true")
        if self.persistence_enabled:
            raise RuntimeAnalyticsPolicyError("persistence_enabled must be false")
        if self.transmission_enabled:
            raise RuntimeAnalyticsPolicyError("transmission_enabled must be false")
        if not self.installation_id_required:
            raise RuntimeAnalyticsPolicyError("installation_id_required must be true")
        if not self.installation_id_only_identifier:
            raise RuntimeAnalyticsPolicyError(
                "installation_id_only_identifier must be true"
            )
        if not self.requires_prior_privacy_projection:
            raise RuntimeAnalyticsPolicyError(
                "requires_prior_privacy_projection must be true"
            )
        if not self.category_runtime_only:
            raise RuntimeAnalyticsPolicyError("category_runtime_only must be true")

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "category_runtime_only": self.category_runtime_only,
            "installation_id_only_identifier": self.installation_id_only_identifier,
            "installation_id_required": self.installation_id_required,
            "limitations": list(self.limitations),
            "local_collection_allowed": self.local_collection_allowed,
            "persistence_enabled": self.persistence_enabled,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "requires_prior_privacy_projection": self.requires_prior_privacy_projection,
            "review_status": self.review_status,
            "schema_id": self.schema_id,
            "schema_token": self.schema_token,
            "schema_version": self.schema_version,
            "transmission_enabled": self.transmission_enabled,
        }

    @classmethod
    def default(cls) -> CommunityRuntimeAnalyticsPolicy:
        return cls()


def default_runtime_analytics_policy() -> CommunityRuntimeAnalyticsPolicy:
    return CommunityRuntimeAnalyticsPolicy.default()


def classify_os_family(system: str | None = None) -> str:
    value = (system if system is not None else platform.system()).strip().lower()
    if value in {"linux"}:
        return "linux"
    if value in {"darwin", "macos", "mac os", "mac os x"}:
        return "macos"
    if value in {"windows", "win32", "cygwin"}:
        return "windows"
    if value in _APPROVED_OS_FAMILIES:
        return value
    return "other"


def classify_architecture(machine: str | None = None) -> str:
    value = (machine if machine is not None else platform.machine()).strip().lower()
    if value in {"x86_64", "amd64", "x64"}:
        return "x86_64"
    if value in {"arm64", "aarch64"}:
        return "arm64"
    if value in _APPROVED_ARCHITECTURES:
        return value
    return "other"


def classify_runtime_version(
    major: int | None = None,
    minor: int | None = None,
) -> str:
    maj = sys.version_info.major if major is None else major
    min_ = sys.version_info.minor if minor is None else minor
    return f"{maj}.{min_}"


def classify_release_adoption(cli_version: str) -> str:
    parts = cli_version.strip().split(".")
    if len(parts) < 2:
        return "0.0"
    major, minor = parts[0], parts[1]
    if not major.isdigit() or not minor.isdigit():
        return "0.0"
    return f"{int(major)}.{int(minor)}"


def is_safe_cli_version(value: str) -> bool:
    return bool(value) and len(value) <= 32 and bool(_VERSION_RE.match(value))


def is_safe_runtime_version(value: str) -> bool:
    return bool(_RUNTIME_VERSION_RE.match(value))


def is_safe_release_adoption(value: str) -> bool:
    return bool(_ADOPTION_RE.match(value))


@dataclass(frozen=True, slots=True)
class RuntimeAnalyticsEvent:
    """Local runtime analytics record (category=runtime).

    ``installation_id`` is the only identifier. Analytics payloads are not
    persisted or transmitted by this slice.
    """

    installation_id: str
    cli_version: str
    os_family: str
    architecture: str
    runtime_version: str
    release_adoption: str
    event_type: str = RUNTIME_ANALYTICS_EVENT_TYPE
    category: str = AnalyticsCategory.RUNTIME.value
    client_name: str = "codestrata_cli"
    lifecycle: str = AnalyticsLifecycle.PROJECTED.value
    schema_version: str = COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION
    policy_version: str = COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    privacy_projection_applied: bool = True
    offline_mode: bool = True
    operation_category: str = "runtime"
    result: str = "success"

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "architecture": self.architecture,
            "category": self.category,
            "cli_version": self.cli_version,
            "client_name": self.client_name,
            "event_type": self.event_type,
            "installation_id": self.installation_id,
            "lifecycle": self.lifecycle,
            "offline_mode": self.offline_mode,
            "operation_category": self.operation_category,
            "os_family": self.os_family,
            "policy_version": self.policy_version,
            "privacy_projection_applied": self.privacy_projection_applied,
            "release_adoption": self.release_adoption,
            "result": self.result,
            "runtime_version": self.runtime_version,
            "schema_version": self.schema_version,
        }

    def to_analytics_event(self) -> AnalyticsEvent:
        """Produce the Slice 10.1 AnalyticsEvent (no installation_id field)."""

        return AnalyticsEvent(
            event_type=self.event_type,
            category=AnalyticsCategory.RUNTIME,
            client_name=self.client_name,
            lifecycle=AnalyticsLifecycle(self.lifecycle),
            schema_version=self.analytics_schema_version,
            policy_version=self.analytics_policy_version,
            privacy_projection_applied=self.privacy_projection_applied,
            offline_mode=self.offline_mode,
            operation_category=self.operation_category,
            result=self.result,
            os_family=self.os_family,
            cli_version=self.cli_version,
            architecture=self.architecture,
            runtime_version=self.runtime_version,
            release_adoption=self.release_adoption,
        )


def build_runtime_analytics_event(
    *,
    identity: AnonymousInstallationIdentity,
    cli_version: str,
    os_family: str,
    architecture: str,
    runtime_version: str,
    release_adoption: str | None = None,
    privacy_projection_applied: bool = True,
) -> RuntimeAnalyticsEvent:
    adoption = (
        release_adoption
        if release_adoption is not None
        else classify_release_adoption(cli_version)
    )
    return RuntimeAnalyticsEvent(
        installation_id=identity.installation_id,
        cli_version=cli_version,
        os_family=os_family,
        architecture=architecture,
        runtime_version=runtime_version,
        release_adoption=adoption,
        privacy_projection_applied=privacy_projection_applied,
    )


def collect_runtime_analytics(
    *,
    home: Path | None = None,
    identity: AnonymousInstallationIdentity | None = None,
    cli_version: str | None = None,
    os_family: str | None = None,
    architecture: str | None = None,
    runtime_version: str | None = None,
    release_adoption: str | None = None,
    policy: CommunityRuntimeAnalyticsPolicy | None = None,
) -> RuntimeAnalyticsEvent:
    """Locally construct a runtime analytics event (no transmit / no analytics persist)."""

    from codestrata.telemetry.analytics.runtime_analytics_projection import (
        project_runtime_analytics_event,
    )
    from codestrata.telemetry.analytics.runtime_analytics_validation import (
        validate_runtime_analytics_event,
    )

    active = policy or default_runtime_analytics_policy()
    active.validate()

    if identity is None:
        identity, _, _ = ensure_anonymous_installation_identity(home=home)
    if not is_uuid_v4(identity.installation_id):
        from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode

        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    resolved_cli = (cli_version if cli_version is not None else get_package_version()).strip()
    resolved_os = classify_os_family(os_family) if os_family is not None else classify_os_family()
    resolved_arch = (
        classify_architecture(architecture)
        if architecture is not None
        else classify_architecture()
    )
    resolved_runtime = (
        runtime_version
        if runtime_version is not None
        else classify_runtime_version()
    )
    event = build_runtime_analytics_event(
        identity=identity,
        cli_version=resolved_cli,
        os_family=resolved_os,
        architecture=resolved_arch,
        runtime_version=resolved_runtime,
        release_adoption=release_adoption,
        privacy_projection_applied=True,
    )
    projected = project_runtime_analytics_event(event, policy=active)
    validate_runtime_analytics_event(event, policy=active)
    # Touch projected for fail-closed construction without persisting.
    _ = projected
    return event


__all__ = [
    "COMMUNITY_RUNTIME_ANALYTICS_POLICY_ID",
    "COMMUNITY_RUNTIME_ANALYTICS_POLICY_URN",
    "COMMUNITY_RUNTIME_ANALYTICS_POLICY_VERSION",
    "COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_ID",
    "COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_URN",
    "COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION",
    "RUNTIME_ANALYTICS_EVENT_TYPE",
    "CommunityRuntimeAnalyticsPolicy",
    "RuntimeAnalyticsEvent",
    "RuntimeAnalyticsPolicyError",
    "build_runtime_analytics_event",
    "classify_architecture",
    "classify_os_family",
    "classify_release_adoption",
    "classify_runtime_version",
    "collect_runtime_analytics",
    "default_runtime_analytics_policy",
    "is_safe_cli_version",
    "is_safe_release_adoption",
    "is_safe_runtime_version",
]
