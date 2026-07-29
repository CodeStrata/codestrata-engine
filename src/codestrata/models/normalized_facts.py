"""Normalized repository fact groups for modernization analysis."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field

_CANONICAL_TECHNOLOGY_NAMES = {
    "maven": "Maven",
    "gradle": "Gradle",
    "ant": "Ant",
    "npm": "npm",
    "composer": "Composer",
    "python": "Python",
    "go": "Go",
    "rust": "Rust",
}


def merge_unique_strings(left: list[str], right: list[str]) -> list[str]:
    """Merge string lists while preserving first-seen order."""

    return list(dict.fromkeys([*left, *right]))


def canonical_technology_name(name: str) -> str:
    """Return a canonical display name for known technology identifiers."""

    return _CANONICAL_TECHNOLOGY_NAMES.get(name.casefold(), name)


def merge_unique_strings_case_insensitive(
    left: list[str],
    right: list[str],
) -> list[str]:
    """Merge strings case-insensitively, preferring canonical display names."""

    merged: list[str] = []
    index_by_key: dict[str, int] = {}

    for value in [*left, *right]:
        key = value.casefold()
        preferred = _CANONICAL_TECHNOLOGY_NAMES.get(key, value)

        if key in index_by_key:
            existing = merged[index_by_key[key]]
            merged[index_by_key[key]] = _prefer_display_string(existing, preferred)
            continue

        index_by_key[key] = len(merged)
        merged.append(preferred)

    return merged


def _prefer_display_string(left: str, right: str) -> str:
    """Prefer canonical or Title Case forms when merging aliases."""

    left_canonical = _CANONICAL_TECHNOLOGY_NAMES.get(left.casefold())
    if left_canonical is not None:
        return left_canonical

    right_canonical = _CANONICAL_TECHNOLOGY_NAMES.get(right.casefold())
    if right_canonical is not None:
        return right_canonical

    left_upper = sum(character.isupper() for character in left)
    right_upper = sum(character.isupper() for character in right)

    if right_upper > left_upper:
        return right

    return left


def merge_optional_bool(
    left: bool | None,
    right: bool | None,
) -> bool | None:
    """Merge optional booleans without letting missing values overwrite."""

    if left is None:
        return right

    if right is None:
        return left

    return left or right


def merge_optional_int(
    left: int | None,
    right: int | None,
) -> int | None:
    """Merge optional absolute counts without letting missing values overwrite."""

    if left is None:
        return right

    if right is None:
        return left

    return max(left, right)


class StructureFacts(BaseModel):
    """Repository structure signals."""

    file_count: int | None = None
    source_file_count: int | None = None
    test_file_count: int | None = None
    application_count: int | None = None
    has_tests: bool | None = None
    architecture_layers: list[str] = Field(default_factory=list)

    def merge(self, other: StructureFacts) -> Self:
        """Merge independently produced structure facts."""

        return self.model_copy(
            update={
                "file_count": merge_optional_int(
                    self.file_count,
                    other.file_count,
                ),
                "source_file_count": merge_optional_int(
                    self.source_file_count,
                    other.source_file_count,
                ),
                "test_file_count": merge_optional_int(
                    self.test_file_count,
                    other.test_file_count,
                ),
                "application_count": merge_optional_int(
                    self.application_count,
                    other.application_count,
                ),
                "has_tests": merge_optional_bool(
                    self.has_tests,
                    other.has_tests,
                ),
                "architecture_layers": merge_unique_strings(
                    self.architecture_layers,
                    other.architecture_layers,
                ),
            }
        )


class TechnologyFacts(BaseModel):
    """Normalized technology detection signals."""

    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    build_tools: list[str] = Field(default_factory=list)
    test_frameworks: list[str] = Field(default_factory=list)
    detected_technologies: list[str] = Field(default_factory=list)

    def merge(self, other: TechnologyFacts) -> Self:
        """Merge independently produced technology facts."""

        return self.model_copy(
            update={
                "programming_languages": merge_unique_strings_case_insensitive(
                    self.programming_languages,
                    other.programming_languages,
                ),
                "frameworks": merge_unique_strings_case_insensitive(
                    self.frameworks,
                    other.frameworks,
                ),
                "build_tools": merge_unique_strings_case_insensitive(
                    self.build_tools,
                    other.build_tools,
                ),
                "test_frameworks": merge_unique_strings_case_insensitive(
                    self.test_frameworks,
                    other.test_frameworks,
                ),
                "detected_technologies": merge_unique_strings_case_insensitive(
                    self.detected_technologies,
                    other.detected_technologies,
                ),
            }
        )


class SecurityFacts(BaseModel):
    """Security risk summary signals."""

    sensitive_file_count: int | None = None
    secret_finding_count: int | None = None
    weak_crypto_count: int | None = None
    dangerous_execution_count: int | None = None

    def merge(self, other: SecurityFacts) -> Self:
        """Merge independently produced security facts."""

        return self.model_copy(
            update={
                "sensitive_file_count": merge_optional_int(
                    self.sensitive_file_count,
                    other.sensitive_file_count,
                ),
                "secret_finding_count": merge_optional_int(
                    self.secret_finding_count,
                    other.secret_finding_count,
                ),
                "weak_crypto_count": merge_optional_int(
                    self.weak_crypto_count,
                    other.weak_crypto_count,
                ),
                "dangerous_execution_count": merge_optional_int(
                    self.dangerous_execution_count,
                    other.dangerous_execution_count,
                ),
            }
        )


class CloudReadinessFacts(BaseModel):
    """Cloud and infrastructure readiness signals."""

    has_docker: bool | None = None
    has_devcontainer: bool | None = None
    has_docker_compose: bool | None = None
    has_kubernetes: bool | None = None
    has_helm: bool | None = None
    has_terraform: bool | None = None
    has_cloudformation: bool | None = None
    has_serverless: bool | None = None
    cloud_capabilities: list[str] = Field(default_factory=list)

    def merge(self, other: CloudReadinessFacts) -> Self:
        """Merge independently produced cloud-readiness facts."""

        return self.model_copy(
            update={
                "has_docker": merge_optional_bool(
                    self.has_docker,
                    other.has_docker,
                ),
                "has_devcontainer": merge_optional_bool(
                    self.has_devcontainer,
                    other.has_devcontainer,
                ),
                "has_docker_compose": merge_optional_bool(
                    self.has_docker_compose,
                    other.has_docker_compose,
                ),
                "has_kubernetes": merge_optional_bool(
                    self.has_kubernetes,
                    other.has_kubernetes,
                ),
                "has_helm": merge_optional_bool(
                    self.has_helm,
                    other.has_helm,
                ),
                "has_terraform": merge_optional_bool(
                    self.has_terraform,
                    other.has_terraform,
                ),
                "has_cloudformation": merge_optional_bool(
                    self.has_cloudformation,
                    other.has_cloudformation,
                ),
                "has_serverless": merge_optional_bool(
                    self.has_serverless,
                    other.has_serverless,
                ),
                "cloud_capabilities": merge_unique_strings(
                    self.cloud_capabilities,
                    other.cloud_capabilities,
                ),
            }
        )


class ArchitectureFacts(BaseModel):
    """Application architecture signals."""

    has_api_layer: bool | None = None
    has_service_layer: bool | None = None
    has_persistence_layer: bool | None = None
    has_domain_layer: bool | None = None
    is_multi_application: bool | None = None

    def merge(self, other: ArchitectureFacts) -> Self:
        """Merge independently produced architecture facts."""

        return self.model_copy(
            update={
                "has_api_layer": merge_optional_bool(
                    self.has_api_layer,
                    other.has_api_layer,
                ),
                "has_service_layer": merge_optional_bool(
                    self.has_service_layer,
                    other.has_service_layer,
                ),
                "has_persistence_layer": merge_optional_bool(
                    self.has_persistence_layer,
                    other.has_persistence_layer,
                ),
                "has_domain_layer": merge_optional_bool(
                    self.has_domain_layer,
                    other.has_domain_layer,
                ),
                "is_multi_application": merge_optional_bool(
                    self.is_multi_application,
                    other.is_multi_application,
                ),
            }
        )
