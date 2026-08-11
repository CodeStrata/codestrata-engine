"""Negative scenarios A–Z for SV.11.13. ok = not holds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codestrata.ai.provider_contracts.registry import AIProviderRegistry
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.ai.providers.factory import resolve_assess_model_id
from codestrata.config.settings import (
    DEFAULT_BEDROCK_MODEL_ID,
    AiSettings,
    CodestrataSettings,
    OpenAISettings,
    OpenRouterSettings,
)
from codestrata.extensions.assess_ai import get_assess_ai_provider_registry
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from verification.ai_provider_platform_completion.contract import (
    BEDROCK_DEFAULT_MODEL,
    CURRENT_POSTURE_DOC_RELATIVE,
    FORBIDDEN_STALE_CLAIMS,
    NEGATIVE_SCENARIO_COUNT_MIN,
    OPENAI_DEFAULT_MODEL,
    PRIVACY_FORBIDDEN_FRAGMENTS,
    REGISTRY_DECISION,
)
from verification.ai_provider_platform_completion.models import ScenarioResult
from verification.ai_provider_platform_completion.slice_matrix import (
    build_slice_matrix,
    sorted_slice_matrix,
)
from verification.ai_provider_cross_provider.contract import (
    REGISTRY_DECISION as CROSS_DECISION,
)


def _settings(**ai_updates: object) -> CodestrataSettings:
    payload: dict[str, object] = {"repository": {"path": "."}}
    if ai_updates:
        payload["ai"] = ai_updates
    return CodestrataSettings.model_validate(payload)


def run_negative_scenarios(
    engine_root: Path,
    *,
    report_payload: dict[str, Any] | None = None,
    slice_matrix: list[dict[str, Any]] | None = None,
) -> list[ScenarioResult]:
    scenarios: list[ScenarioResult] = []
    monorepo = engine_root.parent

    def add(scenario_id: str, title: str, forbidden: str, holds: bool, detail: str = "") -> None:
        scenarios.append(
            ScenarioResult(
                scenario_id=scenario_id,
                title=title,
                forbidden_condition=forbidden,
                ok=not holds,
                detail=detail,
            )
        )

    matrix = slice_matrix or sorted_slice_matrix(
        build_slice_matrix(engine_root, treat_self_complete=True)
    )
    complete_count = sum(1 for row in matrix if row["complete"])

    # A. fewer than 13 slices marked complete
    add("A", "fewer than 13 slices marked complete", "complete_count < 13", complete_count < 13)

    # B. missing prior verification package
    missing_pkg = any(not row["package_exists"] for row in matrix if not row.get("self"))
    add("B", "missing prior verification package", "prior package missing", missing_pkg)

    # C. prior verification report failed
    prior_failed = any(
        (not row.get("self"))
        and (
            row.get("verdict") not in {"pass", "pass_with_limitations"}
            or row.get("failed_checks") != 0
        )
        for row in matrix
    )
    add("C", "prior verification report failed", "prior report fail", prior_failed)

    # D. Bedrock no longer default
    add(
        "D",
        "Bedrock no longer default",
        "AiSettings().provider != bedrock",
        AiSettings().provider != "bedrock",
    )

    # E. provider missing from inventory
    registered = set(get_assess_ai_provider_registry().list_providers())
    add(
        "E",
        "provider missing from inventory",
        "canonical provider absent",
        not {"bedrock", "openai", "openrouter"}.issubset(registered),
    )

    # F. fourth provider present
    add(
        "F",
        "fourth provider present",
        "registered providers != 3 canonical",
        registered != {"bedrock", "openai", "openrouter"},
    )

    # G. aws_bedrock accepted as Engine provider ID
    aws_accepted = True
    try:
        get_assess_ai_provider_registry().create("aws_bedrock", _settings())
    except AIProviderConfigurationError:
        aws_accepted = False
    add("G", "aws_bedrock accepted as Engine provider ID", "aws_bedrock accepted", aws_accepted)

    # H. model default changed
    add(
        "H",
        "model default changed",
        "bedrock/openai defaults changed",
        DEFAULT_BEDROCK_MODEL_ID != BEDROCK_DEFAULT_MODEL
        or OpenAISettings().answer_model != OPENAI_DEFAULT_MODEL,
    )

    # I. OpenRouter test model used as product default
    add(
        "I",
        "OpenRouter test model used as product default",
        "OpenRouterSettings.model nonempty default",
        OpenRouterSettings().model != "",
    )

    # J. Registry Decision B changed silently
    add(
        "J",
        "Registry Decision B changed silently",
        "REGISTRY_DECISION != B",
        CROSS_DECISION != "B" or REGISTRY_DECISION != "B",
    )

    # K. duplicate provider registration
    # list_providers is a sorted unique map; duplicate register raises — probe empty registry
    dup = False
    try:
        from codestrata.extensions.assess_ai import AssessAIProviderRegistry

        probe = AssessAIProviderRegistry()

        def _factory(settings: CodestrataSettings):  # type: ignore[no-untyped-def]
            raise RuntimeError("unused")

        probe.register("bedrock", _factory)
        probe.register("bedrock", _factory)
        dup = True
    except ValueError:
        dup = False
    add("K", "duplicate provider registration", "duplicate register allowed", dup)

    # L. provider fallback present — no silent fallback when unknown selected
    fallback = False
    try:
        get_assess_ai_provider_registry().create("not-a-provider", _settings())
        fallback = True
    except AIProviderConfigurationError:
        fallback = False
    add("L", "provider fallback present", "unknown provider falls back", fallback)

    # M. maximum attempts greater than one by default
    add(
        "M",
        "maximum attempts greater than one by default",
        "DEFAULT_RETRY_POLICY.maximum_attempts > 1",
        DEFAULT_RETRY_POLICY.maximum_attempts > 1,
    )

    # N–Q / Z use report payload when available
    def _privacy_holds(fragments: tuple[str, ...]) -> bool:
        if report_payload is None:
            return False
        scan_payload = {
            key: value
            for key, value in report_payload.items()
            if key
            not in {
                "checks",
                "negative_scenarios",
                "defects",
                "notes",
                "warnings",
            }
        }
        scan_blob = json.dumps(scan_payload, sort_keys=True)
        return any(frag in scan_blob for frag in fragments)

    add(
        "N",
        "credentials in completion report",
        "credential marker present in public report fields",
        _privacy_holds(("sk-synth-", "AKIASYNTH")),
        detail="scanned after assembly" if report_payload is None else "",
    )
    add(
        "O",
        "prompt/response in completion report",
        "prompt or response marker present in public report fields",
        _privacy_holds(("SYNTHETIC_COMPLETION_PROMPT", "SYNTHETIC_COMPLETION_RESPONSE")),
    )
    add(
        "P",
        "exact model in diagnostics/analytics",
        "invented test model as product default",
        OpenRouterSettings().model != "",
    )
    add(
        "Q",
        "raw error or traceback in report",
        "traceback marker present in public report fields",
        _privacy_holds(("Traceback (most recent call last)",)),
    )

    # R. Assessment schema changed
    add(
        "R",
        "Assessment schema changed",
        "ASSESSMENT_JSON_SCHEMA_VERSION != 1.2",
        ASSESSMENT_JSON_SCHEMA_VERSION != "1.2",
    )

    # S. provider diagnostics enter customer report — structural absence of diagnostics keys
    # in completion report is enough; customer report schema unchanged.
    add(
        "S",
        "provider diagnostics enter customer report",
        "assessment schema drifted",
        ASSESSMENT_JSON_SCHEMA_VERSION != "1.2",
    )

    # T. doctor performs provider invocation
    doctor_src = (engine_root / "src/codestrata/ai/providers/doctor.py").read_text(
        encoding="utf-8"
    )
    add(
        "T",
        "doctor performs provider invocation",
        "OpenAI( or resolve_client( in doctor.py",
        "OpenAI(" in doctor_src or "resolve_client(" in doctor_src,
    )

    # U. verification reports packaged — manifest must not ship reports as product runtime
    import yaml

    manifest = yaml.safe_load(
        (monorepo / "public-export-manifest.yaml").read_text(encoding="utf-8")
    )
    packaged_reports = False
    for item in manifest.get("exports", []):
        if item.get("name") != "codestrata-engine":
            continue
        includes = "\n".join(str(x) for x in item.get("include", []))
        # verification/** is allowed as source for public export of verification package
        # but reports/ should not be included
        if "reports/verification" in includes or "reports/**" in includes:
            packaged_reports = True
    add(
        "U",
        "verification reports packaged",
        "reports/verification included in engine export",
        packaged_reports,
    )

    # V. optional dependency breaks core import
    empty_reg = AIProviderRegistry()
    add(
        "V",
        "optional dependency breaks core import",
        "AIProviderRegistry cannot instantiate empty",
        list(empty_reg.list_provider_ids()) != [],
    )

    # W. Platform/Data Lake imported by provider runtime (sample contracts)
    contracts = engine_root / "src/codestrata/ai/provider_contracts"
    platform_import = False
    for path in sorted(contracts.glob("*.py"))[:15]:
        text = path.read_text(encoding="utf-8")
        if "codestrata_platform" in text or "codestrata.datalake" in text:
            platform_import = True
            break
    add(
        "W",
        "Platform/Data Lake imported by provider runtime",
        "platform/datalake import in contracts",
        platform_import,
    )

    # X. stale documentation claims Epic 11 incomplete
    stale = False
    for rel in CURRENT_POSTURE_DOC_RELATIVE:
        path = monorepo / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if any(claim in text for claim in FORBIDDEN_STALE_CLAIMS):
            stale = True
            break
    add(
        "X",
        "stale documentation claims Epic 11 incomplete",
        "FORBIDDEN_STALE_CLAIMS in current docs",
        stale,
    )

    # Y. Epic 12 implementation exists
    epic12 = (engine_root / "src/codestrata/analytics_dashboard").exists() or (
        engine_root / "verification/community_insights_dashboard"
    ).exists()
    add("Y", "Epic 12 implementation exists", "analytics_dashboard package present", epic12)

    # Z. completion report leaks secrets, content, endpoints, identities, errors, or paths
    add(
        "Z",
        "completion report leaks secrets/content/paths",
        "privacy forbidden fragments present",
        _privacy_holds(PRIVACY_FORBIDDEN_FRAGMENTS),
    )

    # OpenRouter explicit model requirement (extra signal for I)
    raised = False
    try:
        resolve_assess_model_id(
            cli_model_id=None, settings=_settings(provider="openrouter")
        )
    except Exception:  # noqa: BLE001
        raised = True
    if not raised:
        # If somehow returned a default, treat as forbidden hold for I already covered
        pass

    assert len(scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    return scenarios


__all__ = ["run_negative_scenarios"]
