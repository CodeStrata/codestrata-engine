"""Parse GitHub Actions workflow files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from codestrata.models import CicdPipeline
from codestrata.services.analyzers.cicd_command_classifier import (
    CicdCommandCategory,
    CicdCommandClassifier,
)
from codestrata.services.analyzers.yaml_pipeline_loader import YamlPipelineLoader


class GitHubActionsParser:
    """Parse GitHub Actions YAML workflow configurations."""

    _CACHE_ACTIONS = (
        "actions/cache",
        "actions/setup-java",
        "actions/setup-node",
        "actions/setup-python",
        "actions/setup-go",
    )

    _ARTIFACT_ACTIONS = (
        "actions/upload-artifact",
        "actions/download-artifact",
    )

    _CONTAINER_ACTIONS = (
        "docker/build-push-action",
        "docker/setup-buildx-action",
        "docker/login-action",
    )

    def __init__(
        self,
        loader: YamlPipelineLoader | None = None,
        command_classifier: CicdCommandClassifier | None = None,
    ) -> None:
        """Initialize the GitHub Actions parser."""

        self._loader = loader or YamlPipelineLoader()
        self._command_classifier = command_classifier or CicdCommandClassifier()

    def parse(
        self,
        workflow_path: Path,
        relative_path: str,
    ) -> CicdPipeline:
        """Parse a GitHub Actions workflow file."""

        workflow_data = self._loader.load(workflow_path)

        workflow_name = self._loader.optional_string(workflow_data.get("name"))

        triggers = self._parse_triggers(workflow_data.get("on"))

        jobs_data = self._loader.mapping(workflow_data.get("jobs"))

        job_names: list[str] = []
        commands: list[str] = []
        actions: list[str] = []

        uses_containers = False
        uses_matrix_builds = False
        uses_caching = False
        uses_artifacts = False

        for job_name, job_value in jobs_data.items():
            job = self._loader.mapping(job_value)

            if not job:
                continue

            job_names.append(job_name)

            uses_containers = uses_containers or self._job_uses_container(job)

            uses_matrix_builds = uses_matrix_builds or self._job_uses_matrix(job)

            steps = job.get("steps")

            if not isinstance(steps, list):
                continue

            for step_value in steps:
                step = self._loader.mapping(step_value)

                if not step:
                    continue

                step_commands = self._extract_commands(step)
                step_action = self._loader.optional_string(step.get("uses"))

                commands.extend(step_commands)

                if step_action is None:
                    continue

                actions.append(step_action)

                normalized_action = step_action.lower()

                uses_caching = uses_caching or self._step_enables_cache(
                    step=step,
                    action=normalized_action,
                )

                uses_artifacts = uses_artifacts or any(
                    artifact_action in normalized_action
                    for artifact_action in self._ARTIFACT_ACTIONS
                )

                uses_containers = uses_containers or any(
                    container_action in normalized_action
                    for container_action in self._CONTAINER_ACTIONS
                )

        classified_commands = self._command_classifier.classify_many(
            self._unique([*commands, *actions])
        )

        return CicdPipeline(
            provider="github-actions",
            path=relative_path,
            pipeline_name=(workflow_name or self._pipeline_name(relative_path)),
            triggers=self._unique(triggers),
            jobs=self._unique(job_names),
            build_commands=classified_commands[CicdCommandCategory.BUILD],
            test_commands=classified_commands[CicdCommandCategory.TEST],
            deployment_commands=classified_commands[CicdCommandCategory.DEPLOYMENT],
            security_commands=classified_commands[CicdCommandCategory.SECURITY],
            uses_containers=uses_containers,
            uses_matrix_builds=uses_matrix_builds,
            uses_caching=uses_caching,
            uses_artifacts=uses_artifacts,
            metadata={
                "job_count": len(job_names),
                "commands": self._unique(commands),
                "actions": self._unique(actions),
                "packaging_commands": classified_commands[CicdCommandCategory.PACKAGING],
                "infrastructure_commands": classified_commands[CicdCommandCategory.INFRASTRUCTURE],
                "database_commands": classified_commands[CicdCommandCategory.DATABASE],
            },
        )

    def _parse_triggers(
        self,
        trigger_value: object,
    ) -> list[str]:
        """Extract workflow trigger names."""

        if isinstance(trigger_value, str):
            return [trigger_value]

        if isinstance(trigger_value, list):
            return [value for value in trigger_value if isinstance(value, str)]

        trigger_mapping = self._loader.mapping(trigger_value)

        return list(trigger_mapping)

    def _extract_commands(
        self,
        step: dict[str, Any],
    ) -> list[str]:
        """Extract shell commands from a workflow step."""

        run_command = self._loader.optional_string(step.get("run"))

        if run_command is None:
            return []

        return [
            command for command in (line.strip() for line in run_command.splitlines()) if command
        ]

    def _job_uses_container(
        self,
        job: Mapping[str, Any],
    ) -> bool:
        """Determine whether a job uses containers or services."""

        return job.get("container") is not None or job.get("services") is not None

    def _job_uses_matrix(
        self,
        job: Mapping[str, Any],
    ) -> bool:
        """Determine whether a job uses a matrix strategy."""

        strategy = self._loader.mapping(job.get("strategy"))

        return strategy.get("matrix") is not None

    def _step_enables_cache(
        self,
        step: dict[str, Any],
        action: str,
    ) -> bool:
        """Determine whether an action step enables caching."""

        if "actions/cache" in action:
            return True

        if not any(cache_action in action for cache_action in self._CACHE_ACTIONS):
            return False

        with_values = self._loader.mapping(step.get("with"))

        cache_value = with_values.get("cache")

        if isinstance(cache_value, str):
            return bool(cache_value.strip())

        return cache_value not in {
            None,
            "",
            False,
        }

    def _pipeline_name(
        self,
        relative_path: str,
    ) -> str:
        """Infer a workflow name from its filename."""

        file_name = relative_path.replace(
            "\\",
            "/",
        ).rsplit("/", maxsplit=1)[-1]

        for suffix in (".yml", ".yaml"):
            if file_name.endswith(suffix):
                return file_name[: -len(suffix)]

        return file_name

    def _unique(
        self,
        values: list[str],
    ) -> list[str]:
        """Deduplicate strings while preserving order."""

        return list(dict.fromkeys(values))
