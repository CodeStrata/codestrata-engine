"""Structured dependency facts discovered in a repository."""

from __future__ import annotations

from collections.abc import Callable
from typing import Self

from pydantic import BaseModel, Field


class DependencyManifest(BaseModel):
    """A dependency manifest discovered in the repository."""

    path: str
    ecosystem: str
    manifest_type: str
    lockfile: bool = False

    has_version_management: bool = False
    version_management_source: str | None = None


class Dependency(BaseModel):
    """A direct dependency declared by the repository."""

    name: str
    version: str | None = None
    ecosystem: str
    scope: str = "runtime"
    manifest_path: str

    categories: list[str] = Field(default_factory=list)

    dynamic_version: bool = False
    unmanaged_version: bool = False

    version_managed: bool = False
    version_source: str | None = None


class DependencyFacts(BaseModel):
    """Structured dependency information for a repository."""

    manifests: list[DependencyManifest] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)

    dependency_count: int = 0
    direct_dependency_count: int = 0
    development_dependency_count: int = 0
    test_dependency_count: int = 0

    outdated_dependencies: list[str] = Field(default_factory=list)

    framework_dependencies: list[str] = Field(default_factory=list)
    database_drivers: list[str] = Field(default_factory=list)
    cloud_sdks: list[str] = Field(default_factory=list)
    logging_libraries: list[str] = Field(default_factory=list)
    testing_libraries: list[str] = Field(default_factory=list)
    security_libraries: list[str] = Field(default_factory=list)

    dynamic_version_dependencies: list[str] = Field(default_factory=list)
    unmanaged_version_dependencies: list[str] = Field(default_factory=list)

    def merge(self, other: DependencyFacts) -> Self:
        """Merge independently produced dependency facts."""

        manifests = _merge_models(
            self.manifests,
            other.manifests,
            key=lambda manifest: (
                manifest.path,
                manifest.ecosystem,
                manifest.manifest_type,
            ),
        )

        dependencies = _merge_models(
            self.dependencies,
            other.dependencies,
            key=lambda dependency: (
                dependency.name,
                dependency.ecosystem,
                dependency.scope,
                dependency.manifest_path,
            ),
        )

        return self.model_copy(
            update={
                "manifests": manifests,
                "dependencies": dependencies,
                "dependency_count": len(dependencies),
                "direct_dependency_count": len(dependencies),
                "development_dependency_count": sum(
                    dependency.scope == "development" for dependency in dependencies
                ),
                "test_dependency_count": sum(
                    dependency.scope == "test" for dependency in dependencies
                ),
                "outdated_dependencies": _merge_unique(
                    self.outdated_dependencies,
                    other.outdated_dependencies,
                ),
                "framework_dependencies": _merge_unique(
                    self.framework_dependencies,
                    other.framework_dependencies,
                ),
                "database_drivers": _merge_unique(
                    self.database_drivers,
                    other.database_drivers,
                ),
                "cloud_sdks": _merge_unique(
                    self.cloud_sdks,
                    other.cloud_sdks,
                ),
                "logging_libraries": _merge_unique(
                    self.logging_libraries,
                    other.logging_libraries,
                ),
                "testing_libraries": _merge_unique(
                    self.testing_libraries,
                    other.testing_libraries,
                ),
                "security_libraries": _merge_unique(
                    self.security_libraries,
                    other.security_libraries,
                ),
                "dynamic_version_dependencies": _merge_unique(
                    self.dynamic_version_dependencies,
                    other.dynamic_version_dependencies,
                ),
                "unmanaged_version_dependencies": _merge_unique(
                    self.unmanaged_version_dependencies,
                    other.unmanaged_version_dependencies,
                ),
            }
        )


def _merge_unique(left: list[str], right: list[str]) -> list[str]:
    return list(dict.fromkeys([*left, *right]))


def _merge_models[T](
    left: list[T],
    right: list[T],
    key: Callable[[T], object],
) -> list[T]:
    merged: dict[object, T] = {}

    for item in [*left, *right]:
        merged[key(item)] = item

    return list(merged.values())
