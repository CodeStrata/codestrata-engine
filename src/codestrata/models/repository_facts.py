"""Aggregated structured facts collected from repository analyzers."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel

from codestrata.models.build_facts import BuildFacts
from codestrata.models.cicd import CicdFacts
from codestrata.models.dependency_facts import DependencyFacts
from codestrata.models.normalized_facts import (
    ArchitectureFacts,
    CloudReadinessFacts,
    SecurityFacts,
    StructureFacts,
    TechnologyFacts,
)


class RepositoryFacts(BaseModel):
    """Combined repository facts produced across analyzers."""

    structure: StructureFacts | None = None
    technology: TechnologyFacts | None = None
    build: BuildFacts | None = None
    dependencies: DependencyFacts | None = None
    cicd: CicdFacts | None = None
    security: SecurityFacts | None = None
    cloud: CloudReadinessFacts | None = None
    architecture: ArchitectureFacts | None = None

    def merge(self, other: RepositoryFacts) -> Self:
        """Merge independently produced repository facts."""

        return self.model_copy(
            update={
                "structure": self._merge_structure(other),
                "technology": self._merge_technology(other),
                "build": self._merge_build(other),
                "dependencies": self._merge_dependencies(other),
                "cicd": self._merge_cicd(other),
                "security": self._merge_security(other),
                "cloud": self._merge_cloud(other),
                "architecture": self._merge_architecture(other),
            }
        )

    def _merge_structure(
        self,
        other: RepositoryFacts,
    ) -> StructureFacts | None:
        if self.structure is None:
            return other.structure

        if other.structure is None:
            return self.structure

        return self.structure.merge(other.structure)

    def _merge_technology(
        self,
        other: RepositoryFacts,
    ) -> TechnologyFacts | None:
        if self.technology is None:
            return other.technology

        if other.technology is None:
            return self.technology

        return self.technology.merge(other.technology)

    def _merge_build(
        self,
        other: RepositoryFacts,
    ) -> BuildFacts | None:
        if self.build is None:
            return other.build

        if other.build is None:
            return self.build

        return self.build.merge(other.build)

    def _merge_dependencies(
        self,
        other: RepositoryFacts,
    ) -> DependencyFacts | None:
        if self.dependencies is None:
            return other.dependencies

        if other.dependencies is None:
            return self.dependencies

        return self.dependencies.merge(other.dependencies)

    def _merge_cicd(
        self,
        other: RepositoryFacts,
    ) -> CicdFacts | None:
        if self.cicd is None:
            return other.cicd

        if other.cicd is None:
            return self.cicd

        return self.cicd.merge(other.cicd)

    def _merge_security(
        self,
        other: RepositoryFacts,
    ) -> SecurityFacts | None:
        if self.security is None:
            return other.security

        if other.security is None:
            return self.security

        return self.security.merge(other.security)

    def _merge_cloud(
        self,
        other: RepositoryFacts,
    ) -> CloudReadinessFacts | None:
        if self.cloud is None:
            return other.cloud

        if other.cloud is None:
            return self.cloud

        return self.cloud.merge(other.cloud)

    def _merge_architecture(
        self,
        other: RepositoryFacts,
    ) -> ArchitectureFacts | None:
        if self.architecture is None:
            return other.architecture

        if other.architecture is None:
            return self.architecture

        return self.architecture.merge(other.architecture)
