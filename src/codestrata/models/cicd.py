"""Domain models for CI/CD pipeline analysis."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field


class CicdPipeline(BaseModel):
    """A detected CI/CD pipeline configuration."""

    provider: str
    path: str
    pipeline_name: str | None = None

    triggers: list[str] = Field(default_factory=list)
    jobs: list[str] = Field(default_factory=list)

    build_commands: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    deployment_commands: list[str] = Field(default_factory=list)
    security_commands: list[str] = Field(default_factory=list)

    uses_containers: bool = False
    uses_matrix_builds: bool = False
    uses_caching: bool = False
    uses_artifacts: bool = False

    metadata: dict[str, object] = Field(default_factory=dict)


class CicdFacts(BaseModel):
    """Repository-level CI/CD facts."""

    pipelines: list[CicdPipeline] = Field(default_factory=list)

    providers: list[str] = Field(default_factory=list)
    ci_platforms: list[str] = Field(default_factory=list)
    pipeline_files: list[str] = Field(default_factory=list)

    pipeline_count: int = 0
    job_count: int = 0

    has_ci: bool = False
    has_build: bool = False
    has_tests: bool = False
    has_deployment: bool = False
    has_deployment_workflow: bool = False
    has_security_scanning: bool = False

    uses_containers: bool = False
    uses_matrix_builds: bool = False
    uses_caching: bool = False
    uses_artifacts: bool = False

    def merge(self, other: CicdFacts) -> Self:
        """Merge independently produced CI/CD facts."""

        pipelines = _merge_pipelines(
            self.pipelines,
            other.pipelines,
        )

        return self.model_copy(
            update={
                "pipelines": pipelines,
                "providers": _merge_unique(
                    self.providers,
                    other.providers,
                ),
                "ci_platforms": _merge_unique(
                    self.ci_platforms,
                    other.ci_platforms,
                ),
                "pipeline_files": _merge_unique(
                    self.pipeline_files,
                    other.pipeline_files,
                ),
                "pipeline_count": len(pipelines),
                "job_count": sum(len(pipeline.jobs) for pipeline in pipelines),
                "has_ci": self.has_ci or other.has_ci,
                "has_build": self.has_build or other.has_build,
                "has_tests": self.has_tests or other.has_tests,
                "has_deployment": (self.has_deployment or other.has_deployment),
                "has_deployment_workflow": (
                    self.has_deployment_workflow or other.has_deployment_workflow
                ),
                "has_security_scanning": (
                    self.has_security_scanning or other.has_security_scanning
                ),
                "uses_containers": (self.uses_containers or other.uses_containers),
                "uses_matrix_builds": (self.uses_matrix_builds or other.uses_matrix_builds),
                "uses_caching": (self.uses_caching or other.uses_caching),
                "uses_artifacts": (self.uses_artifacts or other.uses_artifacts),
            }
        )


def _merge_unique(
    left: list[str],
    right: list[str],
) -> list[str]:
    """Merge string lists while preserving insertion order."""

    return list(dict.fromkeys([*left, *right]))


def _merge_pipelines(
    left: list[CicdPipeline],
    right: list[CicdPipeline],
) -> list[CicdPipeline]:
    """Merge pipelines using provider and path as their identity."""

    merged: dict[tuple[str, str], CicdPipeline] = {}

    for pipeline in [*left, *right]:
        merged[
            (
                pipeline.provider,
                pipeline.path,
            )
        ] = pipeline

    return list(merged.values())
