"""CI workflow test-invocation evidence collection."""

from __future__ import annotations

from codestrata.application.evidence.repository_testing.discovery import (
    normalize_relative_path,
)
from codestrata.application.evidence.repository_testing.redact import redact_command_projection
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import TestFrameworkFamily
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    make_ci_evidence_id,
)
from codestrata.domain.evidence.repository_testing.models import CiTestInvocationFactEvidence

_TOOL_PATTERNS: tuple[tuple[str, str, TestFrameworkFamily | None], ...] = (
    ("./mvnw test", "maven", TestFrameworkFamily.SUREFIRE),
    ("mvnw test", "maven", TestFrameworkFamily.SUREFIRE),
    ("./mvnw verify", "maven", TestFrameworkFamily.SUREFIRE),
    ("mvnw verify", "maven", TestFrameworkFamily.SUREFIRE),
    ("mvn test", "maven", TestFrameworkFamily.SUREFIRE),
    ("mvn verify", "maven", TestFrameworkFamily.SUREFIRE),
    ("./gradlew test", "gradle", None),
    ("gradlew test", "gradle", None),
    ("./gradlew build", "gradle", None),
    ("gradlew build", "gradle", None),
    ("./gradlew check", "gradle", None),
    ("gradlew check", "gradle", None),
    ("gradle test", "gradle", None),
    ("npm test", "npm", None),
    ("yarn test", "yarn", None),
    ("pnpm test", "pnpm", None),
    ("pytest", "pytest", TestFrameworkFamily.PYTEST),
    ("vitest", "vitest", TestFrameworkFamily.VITEST),
    ("playwright", "playwright", TestFrameworkFamily.PLAYWRIGHT),
    ("cypress", "cypress", TestFrameworkFamily.CYPRESS),
    ("jest", "jest", TestFrameworkFamily.JEST),
)


def _match_tool(
    command: str,
) -> tuple[str, TestFrameworkFamily | None] | None:
    lower_cmd = command.lower()
    for token, tool, framework in _TOOL_PATTERNS:
        if token in lower_cmd:
            return tool, framework
    # Allow flags between tool and goal (e.g. ./mvnw -B verify).
    has_mvn = "mvnw" in lower_cmd or lower_cmd.strip().startswith("mvn ")
    if has_mvn and any(goal in lower_cmd for goal in (" test", " verify", "\ttest", "\tverify")):
        return "maven", TestFrameworkFamily.SUREFIRE
    if has_mvn and lower_cmd.rstrip().endswith(("test", "verify")):
        return "maven", TestFrameworkFamily.SUREFIRE
    has_gradle = "gradlew" in lower_cmd or lower_cmd.strip().startswith("gradle ")
    if has_gradle and any(
        goal in lower_cmd for goal in (" test", " build", " check", "\ttest", "\tbuild", "\tcheck")
    ):
        return "gradle", None
    if has_gradle and lower_cmd.rstrip().endswith(("test", "build", "check")):
        return "gradle", None
    return None


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_testing_ci_collector",
        extraction_method="ci_workflow_scan",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _nearby_name(lines: list[str], index: int) -> str:
    for offset in range(1, 12):
        prev = index - offset
        if prev < 0:
            break
        stripped = lines[prev].strip()
        lower = stripped.lower()
        if lower.startswith("name:") or lower.startswith("- name:"):
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            return value[:80] or "step"
        if lower.startswith("id:"):
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            return value[:80] or "step"
    return "step"


def collect_ci_facts(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str = "",
) -> tuple[CiTestInvocationFactEvidence, ...]:
    """Collect bounded CI test invocation facts from a workflow file."""

    normalized = normalize_relative_path(path)
    if not normalized:
        return ()

    lines = text.splitlines()
    continue_on_error = any(
        "continue-on-error:" in line.lower() and "true" in line.lower()
        for line in lines
    )
    results: list[CiTestInvocationFactEvidence] = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()
        if "run:" not in lower:
            continue
        command = stripped.split(":", 1)[1].strip() if ":" in stripped else stripped
        # Multi-line run blocks: look at following non-empty line when empty.
        if not command and index + 1 < len(lines):
            command = lines[index + 1].strip()
        matched = _match_tool(command)
        if matched is None:
            continue
        matched_tool, matched_framework = matched

        # Nearby conditional `if:` on this step/job.
        conditional = False
        for offset in range(0, 8):
            prev = index - offset
            if prev < 0:
                break
            if lines[prev].strip().lower().startswith("if:"):
                conditional = True
                break

        job_or_step = _nearby_name(lines, index)
        if job_or_step == "step" and "workflow" in normalized.lower():
            # Keep simple default distinguishable from named steps.
            job_or_step = "workflow" if index < 5 else "step"

        projection = redact_command_projection(command)
        results.append(
            CiTestInvocationFactEvidence(
                evidence_id=make_ci_evidence_id(
                    path=normalized,
                    job=job_or_step,
                    tool=matched_tool,
                ),
                path=normalized,
                job_or_step=job_or_step,
                tool=matched_tool,
                command_projection=projection,
                continue_on_error=continue_on_error,
                conditional=conditional,
                framework=matched_framework,
                provenance=_provenance(
                    normalized, configuration_fingerprint=configuration_fingerprint
                ),
            )
        )

    by_id = {item.evidence_id: item for item in results}
    return tuple(sorted(by_id.values(), key=lambda item: item.evidence_id))
