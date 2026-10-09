"""M03 static CI observations. Configuration is not proof a job ran."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.inventory.models import (
    CiDocumentObservation,
    CiInvocationObservation,
    SupportKind,
)
from codestrata.services.analyzers.cicd_command_classifier import (
    CicdCommandCategory,
    CicdCommandClassifier,
)
from codestrata.services.analyzers.cicd_discovery_analyzer import CicdDiscoveryAnalyzer
from codestrata.services.analyzers.yaml_pipeline_loader import (
    YamlLoadStatus,
    YamlPipelineLoader,
)

_DELEGATED = re.compile(
    r"\b(?:npm run|yarn run|pnpm run|composer run-script|make )\b",
    re.IGNORECASE,
)
_EXPRESSION = re.compile(r"\$\{\{|\$\(")
_LINT = (
    "eslint",
    "ruff",
    "pylint",
    "flake8",
    "checkstyle",
    "prettier",
    "phpcs",
    "dotnet format",
)
_COVERAGE = ("--cov", "coverage ", "nyc ", "jacoco", "codecov", "c8 ")
_GITHUB_PREFIX = ".github/workflows/"
_GITHUB_SUFFIXES = (".yml", ".yaml")


def observe_ci(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    *,
    loader: YamlPipelineLoader | None = None,
    classifier: CicdCommandClassifier | None = None,
) -> tuple[CiDocumentObservation, ...]:
    """Statically observe CI files. Never runs the configured commands."""

    loader = loader or YamlPipelineLoader()
    classifier = classifier or CicdCommandClassifier()
    detector = CicdDiscoveryAnalyzer()
    documents: list[CiDocumentObservation] = []
    for raw in sorted(relative_paths):
        path = raw.replace("\\", "/")
        provider = detector._detect_provider(path)
        if provider is None:
            continue
        text = file_texts.get(path, file_texts.get(raw, ""))
        if provider == "github-actions":
            documents.append(_observe_github(path, text, loader=loader, classifier=classifier))
            continue
        documents.append(
            CiDocumentObservation(
                path=path,
                provider=provider,
                support=SupportKind.DETECTION_ONLY,
                parse_status="detection_only",
                invocations=(
                    CiInvocationObservation(
                        path=path,
                        tool_category="unknown",
                        parser_rule="ci.provider.detection_only",
                        unresolved=True,
                        unresolved_reason="provider_structural_parse_unsupported",
                    ),
                ),
            )
        )
    if not documents:
        return ()
    return tuple(documents)


def _observe_github(
    path: str,
    text: str,
    *,
    loader: YamlPipelineLoader,
    classifier: CicdCommandClassifier,
) -> CiDocumentObservation:
    if not path.startswith(_GITHUB_PREFIX) or not path.endswith(_GITHUB_SUFFIXES):
        return CiDocumentObservation(
            path=path,
            provider="github-actions",
            support=SupportKind.DETECTION_ONLY,
            parse_status="not_applicable",
        )
    document = loader.parse_document(text)
    if document.status is not YamlLoadStatus.OK:
        return CiDocumentObservation(
            path=path,
            provider="github-actions",
            support=SupportKind.STRUCTURAL,
            parse_status=document.status.value,
            invocations=(
                CiInvocationObservation(
                    path=path,
                    line=1,
                    tool_category="unknown",
                    parser_rule="gha.document.malformed",
                    unresolved=True,
                    unresolved_reason=document.reason or document.status.value,
                ),
            ),
        )

    invocations: list[CiInvocationObservation] = []
    jobs = loader.mapping(document.data.get("jobs"))
    for job_name, job_value in jobs.items():
        job = loader.mapping(job_value)
        job_if = loader.optional_string(job.get("if"))
        steps = job.get("steps")
        if not isinstance(steps, list):
            invocations.append(
                CiInvocationObservation(
                    path=path,
                    job=job_name,
                    condition=job_if,
                    tool_category="unknown",
                    parser_rule="gha.job.no_steps",
                    unresolved=True,
                    unresolved_reason="missing_or_non_list_steps",
                )
            )
            continue
        if job_if and not steps:
            invocations.append(_condition_only(path, job_name, job_if, text, classifier))
        for step_value in steps:
            step = loader.mapping(step_value)
            if not step:
                continue
            invocations.extend(
                _step_invocations(
                    path=path,
                    job_name=job_name,
                    job_if=job_if,
                    step=step,
                    text=text,
                    loader=loader,
                    classifier=classifier,
                )
            )
    counts = _category_counts(invocations)
    return CiDocumentObservation(
        path=path,
        provider="github-actions",
        support=SupportKind.STRUCTURAL,
        parse_status=document.status.value,
        invocations=tuple(invocations),
        test_count=counts["test"],
        coverage_count=counts["coverage"],
        lint_count=counts["lint"],
        security_count=counts["security"],
    )


def _step_invocations(
    *,
    path: str,
    job_name: str,
    job_if: str | None,
    step: dict[str, object],
    text: str,
    loader: YamlPipelineLoader,
    classifier: CicdCommandClassifier,
) -> list[CiInvocationObservation]:
    step_if = loader.optional_string(step.get("if"))
    condition = step_if or job_if
    run_command = loader.optional_string(step.get("run"))
    action = loader.optional_string(step.get("uses"))
    items: list[CiInvocationObservation] = []
    if run_command:
        for command in (line.strip() for line in run_command.splitlines()):
            if not command:
                continue
            items.append(
                _command_observation(
                    path=path,
                    job_name=job_name,
                    command=command,
                    condition=condition,
                    text=text,
                    classifier=classifier,
                    uses_action=False,
                )
            )
    if action:
        items.append(
            _command_observation(
                path=path,
                job_name=job_name,
                command=action,
                condition=condition,
                text=text,
                classifier=classifier,
                uses_action=True,
            )
        )
    if not items and condition:
        items.append(_condition_only(path, job_name, condition, text, classifier))
    return items


def _command_observation(
    *,
    path: str,
    job_name: str,
    command: str,
    condition: str | None,
    text: str,
    classifier: CicdCommandClassifier,
    uses_action: bool,
) -> CiInvocationObservation:
    category = _tool_category(command, classifier)
    delegated = bool(_DELEGATED.search(command))
    expression = bool(_EXPRESSION.search(command))
    condition_unresolved = bool(condition and _EXPRESSION.search(condition))
    unresolved = delegated or expression or condition_unresolved
    if uses_action:
        rule = "gha.step.uses.action"
    elif delegated:
        rule = "gha.step.run.delegated_script"
    else:
        rule = "gha.step.run.literal"
    reason = None
    if delegated:
        reason = "delegated_script_body_not_inspected"
    elif expression:
        reason = "command_contains_unresolved_expression"
    elif condition_unresolved:
        reason = "condition_contains_unresolved_expression"
    return CiInvocationObservation(
        path=path,
        line=_line_of(text, command),
        job=job_name,
        literal_command=command,
        condition=condition,
        tool_category=category,
        target=_target(command),
        parser_rule=rule,
        unresolved=unresolved,
        unresolved_reason=reason,
    )


def _condition_only(
    path: str,
    job_name: str,
    condition: str,
    text: str,
    classifier: CicdCommandClassifier,
) -> CiInvocationObservation:
    del classifier
    return CiInvocationObservation(
        path=path,
        line=_line_of(text, condition),
        job=job_name,
        condition=condition,
        tool_category="unknown",
        parser_rule="gha.job.if.expression",
        unresolved=bool(_EXPRESSION.search(condition)),
        unresolved_reason=(
            "condition_contains_unresolved_expression" if _EXPRESSION.search(condition) else None
        ),
    )


def _tool_category(command: str, classifier: CicdCommandClassifier) -> str:
    lowered = command.lower()
    if any(token in lowered for token in _COVERAGE):
        return "coverage"
    if any(token in lowered for token in _LINT):
        return "lint"
    matched = classifier.classify(command)
    if CicdCommandCategory.SECURITY in matched:
        return "security"
    if CicdCommandCategory.TEST in matched:
        return "test"
    if CicdCommandCategory.BUILD in matched:
        return "build"
    return "unknown"


def _target(command: str) -> str | None:
    tokens = command.split()
    return tokens[0] if tokens else None


def _line_of(text: str, needle: str) -> int | None:
    first = needle.splitlines()[0] if needle else ""
    if not first:
        return None
    for index, line in enumerate(text.splitlines(), start=1):
        if first in line:
            return index
    return None


def _category_counts(invocations: Sequence[CiInvocationObservation]) -> dict[str, int]:
    counts = {"test": 0, "coverage": 0, "lint": 0, "security": 0}
    for item in invocations:
        if item.tool_category in counts:
            counts[item.tool_category] += 1
    return counts


def is_github_workflow(relative_path: str) -> bool:
    name = PurePosixPath(relative_path.replace("\\", "/")).as_posix()
    return name.startswith(_GITHUB_PREFIX) and name.endswith(_GITHUB_SUFFIXES)
