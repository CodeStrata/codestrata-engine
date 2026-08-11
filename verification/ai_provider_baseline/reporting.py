"""Assemble, sanitize, and verdict the AI Provider Compatibility Baseline report."""

from __future__ import annotations

import re
from typing import Any

from codestrata.security.redaction import redact_secrets
from verification.ai_provider_baseline.contract import (
    ASSESS_ADVISOR_MAX_OUTPUT_TOKENS,
    ASSESSMENT_SCHEMA_VERSION,
    DEFAULT_ASSESS_PROVIDER,
    DEFAULT_MODEL_IDS,
    ENGINE_PROVIDER_IDS,
    EPIC,
    EXISTING_COUPLING_SURFACE,
    EXPECTED_LIMITATIONS,
    INVOKE_CALLS_PER_ASSESS_RUN,
    MODEL_INVOCATION_DEFAULTS,
    PROVIDER_FAMILY_MAP,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SETTINGS_TIMEOUT_MAX_RETRIES_WIRED_TO_ASSESS_FACTORY,
    SLICE_ID,
    VERIFICATION_ID,
    VERIFICATION_VERSION,
)
from verification.ai_provider_baseline.models import (
    BaselineReport,
    CheckResult,
    CompatibilityRequirement,
    CouplingInventoryEntry,
    IntentionalDifference,
    ScenarioResult,
    build_check_counts,
)

_PATH_PATTERNS = (
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/home/[^\s\"']+"),
)

# Exception *type names* may appear; raw exception *messages* must not.
_EXCEPTION_MESSAGE_PATTERNS = (
    re.compile(r"\bAIProvider\w*Error:\s+[^\n\"']+"),
    re.compile(r"\bValidationError:\s+[^\n\"']+"),
    re.compile(r"\bClientError:\s+[^\n\"']+"),
    re.compile(r"Unsupported assess AI provider\b[^\n\"']*"),
)

FORBIDDEN_REPORT_FRAGMENTS: tuple[str, ...] = (
    "/Users/",
    "/home/",
    "Authorization: Bearer",
    "-----BEGIN",
    "Unsupported assess AI provider",
    "sk-proj-",
)

# Credential-shaped tokens (avoid false positives from prose that names
# prefixes like "AKIA" when documenting what must never appear).
_CREDENTIAL_SHAPE_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
)


def sanitize_text(value: str) -> str:
    """Strip secrets, absolute paths, and raw exception messages from free text."""

    sanitized = redact_secrets(value)
    for pattern in _PATH_PATTERNS:
        sanitized = pattern.sub("[PATH_REDACTED]", sanitized)
    for pattern in _EXCEPTION_MESSAGE_PATTERNS:
        sanitized = pattern.sub("[EXCEPTION_MESSAGE_REDACTED]", sanitized)
    for pattern in _CREDENTIAL_SHAPE_PATTERNS:
        sanitized = pattern.sub("[CREDENTIAL_REDACTED]", sanitized)
    return sanitized


def report_contains_forbidden_leak(blob: str) -> list[str]:
    hits = [token for token in FORBIDDEN_REPORT_FRAGMENTS if token in blob]
    for pattern in _CREDENTIAL_SHAPE_PATTERNS:
        if pattern.search(blob):
            hits.append(pattern.pattern)
    return hits


def sanitize_structure(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {key: sanitize_structure(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_structure(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_structure(item) for item in value]
    return value


def sanitize_check(check: CheckResult) -> CheckResult:
    return CheckResult(
        name=check.name,
        category=check.category,
        ok=check.ok,
        detail=sanitize_text(check.detail),
        evidence=sanitize_structure(check.evidence),
    )


def sanitize_scenario(scenario: ScenarioResult) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        title=sanitize_text(scenario.title),
        forbidden_condition=sanitize_text(scenario.forbidden_condition),
        ok=scenario.ok,
        detail=sanitize_text(scenario.detail),
    )


def build_compatibility_requirements() -> tuple[CompatibilityRequirement, ...]:
    return (
        CompatibilityRequirement(
            requirement_id="CR-1",
            description=(
                "Any future common provider interface must preserve the exact-one-"
                "invoke-per-assess-run contract already relied on by "
                "AiEnrichmentService.run()."
            ),
            rationale=(
                "Retries or multi-call fan-out would change latency, cost, and fail-soft semantics."
            ),
            applies_to=ENGINE_PROVIDER_IDS,
        ),
        CompatibilityRequirement(
            requirement_id="CR-2",
            description=(
                "Any future provider platform must explicitly wire (or explicitly and "
                "visibly continue to not wire) [ai.bedrock]/[ai.openai] "
                "timeout_seconds and max_retries — silent behavior must not change."
            ),
            rationale=(
                "These fields already exist in settings; users may believe they are honored today."
            ),
            applies_to=ENGINE_PROVIDER_IDS,
        ),
        CompatibilityRequirement(
            requirement_id="CR-3",
            description=(
                "Fail-soft must be preserved: an AI provider/parsing/validation failure "
                "must keep `codestrata assess` at exit 0 whenever deterministic reports "
                "are written."
            ),
            rationale=(
                "Community users must never lose deterministic results due to optional AI failure."
            ),
            applies_to=ENGINE_PROVIDER_IDS,
        ),
        CompatibilityRequirement(
            requirement_id="CR-4",
            description=(
                "Engine provider IDs (bedrock, openai) must remain stable identifiers "
                "even if analytics-layer provider_family naming evolves."
            ),
            rationale=(
                "Telemetry provider_family mapping (aws_bedrock) is a separate, "
                "analytics-only concern."
            ),
            applies_to=ENGINE_PROVIDER_IDS,
        ),
        CompatibilityRequirement(
            requirement_id="CR-5",
            description=(
                "A future provider platform must not require real network access or "
                "real credentials to run this baseline's characterization tests."
            ),
            rationale=(
                "Community CI and contributor machines must be able to run "
                "AI-surface tests offline."
            ),
            applies_to=ENGINE_PROVIDER_IDS,
        ),
        CompatibilityRequirement(
            requirement_id="CR-6",
            description=(
                "Default model IDs (amazon.nova-lite-v1:0, gpt-4o-mini) and the default "
                "provider (bedrock) must only change via an explicit, documented "
                "decision — not as a side effect of provider platform work."
            ),
            rationale=(
                "Defaults are user-facing behavior baked into existing configuration and docs."
            ),
            applies_to=ENGINE_PROVIDER_IDS,
        ),
    )


def build_intentional_differences() -> tuple[IntentionalDifference, ...]:
    return (
        IntentionalDifference(
            aspect="request_shape",
            bedrock=(
                "Converse API: {modelId, messages, inferenceConfig{maxTokens,temperature}, system?}"
            ),
            openai=(
                "Chat Completions: model, messages[], temperature, max_tokens, "
                "response_format=json_object"
            ),
            rationale=(
                "Each provider's native request contract is preserved rather than "
                "forced into one shape."
            ),
        ),
        IntentionalDifference(
            aspect="json_mode_enforcement",
            bedrock=(
                "Relies on prompt instruction only ('Respond with a single JSON object only')."
            ),
            openai=(
                "Uses response_format={'type': 'json_object'} in addition to the "
                "prompt instruction."
            ),
            rationale=(
                "OpenAI's Chat Completions API offers native JSON-mode; Bedrock Converse does not."
            ),
        ),
        IntentionalDifference(
            aspect="authentication",
            bedrock=(
                "AWS credential provider chain (profile / env / SSO / instance role) via boto3."
            ),
            openai=(
                "Single environment-variable API key (default OPENAI_API_KEY, configurable name)."
            ),
            rationale="Each provider's native authentication model is preserved unmodified.",
        ),
        IntentionalDifference(
            aspect="optional_extra",
            bedrock="codestrata[bedrock] installs boto3.",
            openai="codestrata[openai] installs the openai SDK.",
            rationale=(
                "Neither dependency is required unless the corresponding provider is selected."
            ),
        ),
        IntentionalDifference(
            aspect="error_mapping_detail",
            bedrock=(
                "Maps botocore ClientError codes (ThrottlingException, AccessDeniedException, ...)."
            ),
            openai=(
                "Maps openai SDK exception class names (RateLimitError, AuthenticationError, ...)."
            ),
            rationale=(
                "Each SDK reports failures through a different mechanism "
                "(error codes vs. exception types)."
            ),
        ),
        IntentionalDifference(
            aspect="analytics_provider_family",
            bedrock="Engine ID 'bedrock' maps to analytics provider_family 'aws_bedrock'.",
            openai=(
                "Engine ID 'openai' maps to analytics provider_family 'openai' (identity mapping)."
            ),
            rationale=(
                "Analytics uses a stable, vendor-neutral family label distinct from "
                "the Engine registry ID."
            ),
        ),
    )


def compute_verdict(
    all_checks: list[CheckResult],
    scenarios: tuple[ScenarioResult, ...],
) -> str:
    failed_checks = [c for c in all_checks if not c.ok]
    failed_scenarios = [s for s in scenarios if not s.ok]
    if failed_checks or failed_scenarios:
        return "fail"
    # PASS_WITH_LIMITATIONS is expected/acceptable: no live credentials/network,
    # and the settings timeout/max_retries wiring gap is a recorded limitation.
    return "pass_with_limitations"


def assemble_report(
    *,
    all_checks: list[CheckResult],
    coupling_inventory: tuple[CouplingInventoryEntry, ...],
    matrices: dict[str, Any],
    negative_scenarios: tuple[ScenarioResult, ...],
) -> BaselineReport:
    sanitized_checks = tuple(sanitize_check(c) for c in all_checks)
    sanitized_matrices = sanitize_structure(matrices)
    sanitized_scenarios = tuple(sanitize_scenario(s) for s in negative_scenarios)
    verdict = compute_verdict(list(sanitized_checks), sanitized_scenarios)

    warnings: list[str] = [
        "No live provider network calls were made; credential/authentication "
        "characterization uses mocked boundaries only.",
        "No real credentials were used anywhere in this suite.",
    ]
    notes: list[str] = [
        "CodeStrata v0.2.0 Epic 11, Slice 11.1 — Existing AI Architecture and "
        "Compatibility Baseline. Characterization only; freezes current behavior.",
        "Does not introduce a common provider interface, provider platform, or "
        "registry redesign. Does not migrate OpenAI/Bedrock. Does not add OpenRouter.",
        "Slice 11.2+ is not started by this package.",
    ]

    return BaselineReport(
        assess_advisor_max_output_tokens=ASSESS_ADVISOR_MAX_OUTPUT_TOKENS,
        assessment_schema_version=ASSESSMENT_SCHEMA_VERSION,
        check_counts=build_check_counts(list(sanitized_checks)),
        checks=sanitized_checks,
        compatibility_requirements=build_compatibility_requirements(),
        coupling_inventory=coupling_inventory,
        default_model_ids=dict(DEFAULT_MODEL_IDS),
        default_provider=DEFAULT_ASSESS_PROVIDER,
        epic=EPIC,
        existing_coupling_surface=EXISTING_COUPLING_SURFACE,
        intentional_differences=build_intentional_differences(),
        invoke_calls_per_assess_run=INVOKE_CALLS_PER_ASSESS_RUN,
        limitations=EXPECTED_LIMITATIONS,
        matrices=sanitized_matrices,
        model_invocation_defaults=dict(MODEL_INVOCATION_DEFAULTS),
        negative_scenarios=sanitized_scenarios,
        notes=tuple(notes),
        provider_family_map=dict(PROVIDER_FAMILY_MAP),
        providers=ENGINE_PROVIDER_IDS,
        schema_name=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        settings_timeout_max_retries_wired=SETTINGS_TIMEOUT_MAX_RETRIES_WIRED_TO_ASSESS_FACTORY,
        slice_id=SLICE_ID,
        verdict=verdict,
        verification_id=VERIFICATION_ID,
        verification_version=VERIFICATION_VERSION,
        warnings=tuple(warnings),
    )


__all__ = [
    "FORBIDDEN_REPORT_FRAGMENTS",
    "assemble_report",
    "build_compatibility_requirements",
    "build_intentional_differences",
    "compute_verdict",
    "report_contains_forbidden_leak",
    "sanitize_check",
    "sanitize_scenario",
    "sanitize_structure",
    "sanitize_text",
]
