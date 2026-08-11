"""Negative scenarios A-Z: checks that forbidden conditions do NOT hold.

Each scenario names a condition that Slice 11.1 must never exhibit (scope
creep, credential leakage, silent AI failure, non-determinism, etc.) and
records whether that forbidden condition was observed. ``ok=True`` means the
forbidden condition did **not** occur.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from codestrata.ai.providers.parsing import sanitize_provider_text
from verification.ai_provider_baseline.models import CheckResult, ScenarioResult

_PROCESS_INVOCATION_CALLS = frozenset(
    {
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "os.system",
        "os.popen",
        "os.spawnl",
        "os.spawnv",
    }
)


def _dotted_call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def _module_shells_out_to_a_process(path: Path) -> bool:
    """AST-based (not text-scan) detection of subprocess/os.system usage.

    Uses structural inspection rather than substring matching so that prose
    describing this very check (e.g. a docstring containing the words "git
    commit" or "subprocess") never self-triggers a false positive.
    """

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name in {"subprocess", "os"} for alias in node.names
        ):
            # A bare `import os` alone is not shelling out; only flag
            # `import subprocess`, which this package has no legitimate use for.
            if any(alias.name == "subprocess" for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            return True
        if isinstance(node, ast.Call):
            dotted = _dotted_call_name(node.func)
            if dotted in _PROCESS_INVOCATION_CALLS:
                return True
    return False


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),
)
_ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/home/[^\s\"']+"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\s\"']+"),
)


def _find_matches(patterns: tuple[re.Pattern[str], ...], text: str) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(pattern.findall(text))
    return hits


def _scenario_from_check(
    scenario_id: str,
    title: str,
    forbidden_condition: str,
    check: CheckResult | None,
) -> ScenarioResult:
    if check is None:
        return ScenarioResult(
            scenario_id=scenario_id,
            title=title,
            forbidden_condition=forbidden_condition,
            ok=False,
            detail="backing check not found in check registry",
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        title=title,
        forbidden_condition=forbidden_condition,
        ok=check.ok,
        detail=check.detail,
    )


def _scenario_t_no_unredacted_secrets_in_error_messages() -> ScenarioResult:
    fake_secret_message = (
        "botocore call failed for AWS_SECRET_ACCESS_KEY=abcd1234efgh5678ijkl "
        "AKIAFAKEEXAMPLE0000 Bearer sk-fake0000000000000000example"
    )
    sanitized = sanitize_provider_text(fake_secret_message)
    hits = _find_matches(_SECRET_PATTERNS, sanitized)
    return ScenarioResult(
        scenario_id="T",
        title="Error messages never leak unredacted secret-shaped tokens",
        forbidden_condition="sanitize_provider_text() output contains a raw sk-/AKIA/Bearer token",
        ok=not hits,
        detail=f"sanitized={sanitized!r}",
    )


def _scenario_x_no_absolute_paths(report_payload_preview: dict[str, object]) -> ScenarioResult:
    from verification.ai_provider_baseline.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_ABSOLUTE_PATH_PATTERNS, text)
    return ScenarioResult(
        scenario_id="X",
        title="Baseline report contains no absolute filesystem paths",
        forbidden_condition=(
            "report JSON contains an absolute macOS, Linux, or Windows user-home path"
        ),
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no absolute-path patterns found",
    )


def _scenario_y_no_secrets_in_report(report_payload_preview: dict[str, object]) -> ScenarioResult:
    from verification.ai_provider_baseline.determinism import canonical_json

    text = canonical_json(report_payload_preview)
    hits = _find_matches(_SECRET_PATTERNS, text)
    return ScenarioResult(
        scenario_id="Y",
        title="Baseline report contains no secret-shaped tokens",
        forbidden_condition="report JSON contains a sk-/AKIA/Bearer-shaped token",
        ok=not hits,
        detail=f"hits={hits[:5]}" if hits else "no secret-shaped tokens found",
    )


def _scenario_z_no_git_commit_invocation(source_root: Path) -> ScenarioResult:
    package_dir = source_root.parent.parent / "verification" / "ai_provider_baseline"
    hits: list[str] = []
    if package_dir.exists():
        for path in sorted(package_dir.glob("*.py")):
            if _module_shells_out_to_a_process(path):
                hits.append(path.name)
    return ScenarioResult(
        scenario_id="Z",
        title="This verification package never invokes git commit",
        forbidden_condition="a module under ai_provider_baseline/ shells out to git commit",
        ok=not hits,
        detail=f"flagged_files={hits}" if hits else "no subprocess/os.system usage in this package",
    )


def build_negative_scenarios(
    source_root: Path,
    *,
    checks_by_name: dict[str, CheckResult],
    report_payload_preview: dict[str, object],
) -> tuple[ScenarioResult, ...]:
    def get(name: str) -> CheckResult | None:
        return checks_by_name.get(name)

    scenarios = [
        _scenario_from_check(
            "A",
            "No real AWS network call is required for authentication characterization",
            "a real botocore network call (sts.get_caller_identity) is made",
            get("aws_session_construction_boundary_is_mockable"),
        ),
        _scenario_from_check(
            "B",
            "No real credentials are used anywhere in this suite",
            "a real (non-placeholder) AWS/OpenAI credential value is used",
            get("openai_api_key_env_presence_scenarios_match_expected"),
        ),
        _scenario_from_check(
            "C",
            "No operational OpenRouter wiring exists outside adapter+contracts",
            "an 'openrouter' token appears under ai/providers/, enrichment, "
            "extensions/assess_ai.py, or config/settings.py",
            get("no_openrouter_references_in_ai_provider_surface"),
        ),
        _scenario_from_check(
            "D",
            "No new common provider interface / provider platform was introduced",
            "a CommonAIProvider/ProviderPlatform/UnifiedAIProvider class exists",
            get("no_new_common_provider_interface_introduced"),
        ),
        _scenario_from_check(
            "E",
            "No new files were added to ai/providers/ beyond the existing 11",
            "ai/providers/ contains a file outside the known baseline set",
            get("ai_providers_directory_has_no_unexpected_new_files"),
        ),
        _scenario_from_check(
            "F",
            "Settings timeout_seconds is not silently wired into the assess factory",
            "extensions/assess_ai.py forwards timeout_seconds= to a provider constructor",
            get("assess_bootstrap_does_not_forward_settings_timeout_seconds"),
        ),
        _scenario_from_check(
            "G",
            "Settings max_retries is not silently wired into assess provider invocation",
            "an assess provider invocation path reads/uses [ai.*].max_retries",
            get("assess_bootstrap_does_not_forward_settings_max_retries"),
        ),
        _scenario_from_check(
            "H",
            "retry_call() is not referenced by production assess providers",
            "bedrock.py or openai_provider.py imports/calls retry_call",
            get("bedrock_provider_does_not_reference_retry_call"),
        ),
        _scenario_from_check(
            "I",
            "Exactly one provider.invoke() call happens per assess run",
            "AiEnrichmentService.run() calls provider.invoke() zero or 2+ times",
            get("ai_enrichment_service_run_invokes_provider_exactly_once"),
        ),
        _scenario_from_check(
            "J",
            "Assessment JSON schema version is unchanged",
            "ASSESSMENT_JSON_SCHEMA_VERSION is not exactly '1.2'",
            get("assessment_json_schema_version_is_1_2"),
        ),
        _scenario_from_check(
            "K",
            "An AI stage failure never propagates out of the assess pipeline",
            "AssessmentCommandError from _run_ai_assessment is bare re-raised",
            get("ai_stage_assessment_command_error_caught_without_reraise"),
        ),
        _scenario_from_check(
            "L",
            "No AI failure status is silently unreported to the customer",
            "a failure AIExecutionStatus has no customer_failure_message()",
            get("every_ai_failure_status_has_a_customer_facing_message"),
        ),
        _scenario_from_check(
            "M",
            "codestrata ai doctor never invokes a model",
            "build_ai_configuration_report() calls a provider .invoke(",
            get("doctor_report_uses_mockable_probe_boundary"),
        ),
        _scenario_from_check(
            "N",
            "codestrata ai doctor output contains no secret-shaped tokens",
            "the doctor report text contains sk-/AKIA/Bearer tokens",
            get("doctor_report_contains_no_secret_shaped_tokens"),
        ),
        _scenario_from_check(
            "O",
            "The default assess provider remains bedrock",
            "CodestrataSettings().ai.provider default is not 'bedrock'",
            get("default_assess_provider_is_bedrock"),
        ),
        _scenario_from_check(
            "P",
            "Default model IDs are unchanged from ground truth",
            "resolved default model IDs differ from amazon.nova-lite-v1:0 / gpt-4o-mini",
            get("default_model_ids_match_ground_truth"),
        ),
        _scenario_from_check(
            "Q",
            "An unsupported provider name never reaches credential resolution",
            "registry.create() with a bogus provider name does anything but raise immediately",
            get("unsupported_provider_raises_configuration_error"),
        ),
        _scenario_from_check(
            "R",
            "Optional extras remain exactly bedrock/openai (no new provider extras)",
            "engine/pyproject.toml declares an extra beyond bedrock/openai/mcp/development",
            get("optional_extras_still_only_bedrock_and_openai"),
        ),
        _scenario_from_check(
            "S",
            "Bedrock request construction exposes only the documented top-level keys",
            "build_converse_request() emits an undocumented top-level key",
            get("bedrock_converse_request_shape"),
        ),
        _scenario_t_no_unredacted_secrets_in_error_messages(),
        _scenario_from_check(
            "U",
            "Well-formed synthetic provider responses never fail extraction",
            "extract_converse_response()/_extract_chat_response() raise on valid fixtures",
            get("bedrock_converse_response_extraction"),
        ),
        _scenario_from_check(
            "V",
            "Malformed usage payloads never raise (they degrade to None fields)",
            "_extract_usage() raises on an empty/None/negative payload",
            get("bedrock_usage_extraction_tolerates_malformed_payloads"),
        ),
        _scenario_from_check(
            "W",
            "Invalid invocation options (temperature/max_output_tokens) are rejected",
            "ModelInvocationOptions accepts temperature=1.5 or max_output_tokens=0",
            get("model_invocation_options_temperature_bounded_0_to_1"),
        ),
        _scenario_x_no_absolute_paths(report_payload_preview),
        _scenario_y_no_secrets_in_report(report_payload_preview),
        _scenario_z_no_git_commit_invocation(source_root),
    ]
    return tuple(sorted(scenarios, key=lambda s: s.scenario_id))


__all__ = ["build_negative_scenarios"]
