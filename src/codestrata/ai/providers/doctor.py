"""Assess AI provider configuration diagnostics (no secrets).

Used by ``codestrata ai`` / ``codestrata ai doctor``. Does not invoke models
or change assessment / enrichment behavior.

Bedrock checks use :func:`probe_aws_session_for_bedrock` — the same profile /
region / session resolution as Bedrock Runtime client creation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from codestrata.ai.aws_config import probe_aws_session_for_bedrock
from codestrata.ai.providers.factory import (
    CODESTRATA_BEDROCK_MODEL_ID_ENV,
    CODESTRATA_OPENAI_MODEL_ID_ENV,
    supported_assess_ai_providers,
)
from codestrata.config.settings import DEFAULT_BEDROCK_MODEL_ID, CodestrataSettings


class ConfigStatus(StrEnum):
    """Human-facing configuration status for a provider."""

    CONFIGURED = "Configured"
    NOT_CONFIGURED = "Not Configured"


@dataclass(frozen=True, slots=True)
class AiCheck:
    """One diagnostic line for AI doctor output."""

    label: str
    ok: bool
    detail: str
    guidance: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderOverview:
    """Non-secret overview of one assess AI provider."""

    name: str
    status: ConfigStatus
    detail: str
    required_env: tuple[str, ...]
    optional_env: tuple[str, ...]
    credential_source: str | None = None
    guidance: str | None = None


@dataclass(frozen=True, slots=True)
class AiConfigurationReport:
    """Full Community AI configuration report (safe to print)."""

    active_provider: str
    supported_providers: tuple[str, ...]
    active_supported: bool
    providers: tuple[ProviderOverview, ...]
    checks: tuple[AiCheck, ...]
    model_id: str
    docs_url: str = "https://docs.codestrata.ai/ai-providers/"


def _bedrock_extra_installed() -> bool:
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False
    return True


def _openai_extra_installed() -> bool:
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def _openai_api_key_present(settings: CodestrataSettings) -> tuple[bool, str]:
    env_name = (settings.ai.openai.api_key_env or "OPENAI_API_KEY").strip() or "OPENAI_API_KEY"
    if os.environ.get(env_name, "").strip():
        return True, f"{env_name} is set (environment)"
    return False, f"{env_name} missing"


def _resolve_model_label(settings: CodestrataSettings) -> str:
    provider = (settings.ai.provider or "bedrock").strip().lower()
    if provider == "openai":
        env_model = os.environ.get(CODESTRATA_OPENAI_MODEL_ID_ENV, "").strip()
        if env_model:
            return env_model
        return (settings.ai.openai.answer_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
    env_model = os.environ.get(CODESTRATA_BEDROCK_MODEL_ID_ENV, "").strip()
    if env_model:
        return env_model
    configured = (settings.ai.bedrock.model_id or "").strip()
    return configured or DEFAULT_BEDROCK_MODEL_ID


def _bedrock_overview(settings: CodestrataSettings) -> ProviderOverview:
    required = ("AWS_REGION (or config / default region)",)
    optional = (
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (or SSO / instance role)",
        CODESTRATA_BEDROCK_MODEL_ID_ENV,
    )
    if not _bedrock_extra_installed():
        return ProviderOverview(
            name="bedrock",
            status=ConfigStatus.NOT_CONFIGURED,
            detail="extra not installed (pip install 'codestrata[bedrock]')",
            required_env=required,
            optional_env=optional,
            guidance="pip install 'codestrata[bedrock]'",
        )

    probe = probe_aws_session_for_bedrock(settings=settings)
    if probe.ok:
        return ProviderOverview(
            name="bedrock",
            status=ConfigStatus.CONFIGURED,
            detail=probe.detail,
            required_env=required,
            optional_env=optional,
            credential_source=probe.credential_source,
        )
    return ProviderOverview(
        name="bedrock",
        status=ConfigStatus.NOT_CONFIGURED,
        detail=probe.detail,
        required_env=required,
        optional_env=optional,
        credential_source=probe.credential_source,
        guidance=probe.guidance,
    )


def _openai_overview(settings: CodestrataSettings) -> ProviderOverview:
    env_name = (settings.ai.openai.api_key_env or "OPENAI_API_KEY").strip() or "OPENAI_API_KEY"
    required = (env_name,)
    optional = (CODESTRATA_OPENAI_MODEL_ID_ENV, "CODESTRATA_OPENAI_API_KEY_ENV")
    if not _openai_extra_installed():
        return ProviderOverview(
            name="openai",
            status=ConfigStatus.NOT_CONFIGURED,
            detail="extra not installed (pip install 'codestrata[openai]')",
            required_env=required,
            optional_env=optional,
            guidance="pip install 'codestrata[openai]'",
        )
    key_ok, key_detail = _openai_api_key_present(settings)
    if key_ok:
        return ProviderOverview(
            name="openai",
            status=ConfigStatus.CONFIGURED,
            detail=key_detail,
            required_env=required,
            optional_env=optional,
            credential_source=f"environment {env_name}",
        )
    return ProviderOverview(
        name="openai",
        status=ConfigStatus.NOT_CONFIGURED,
        detail=key_detail,
        required_env=required,
        optional_env=optional,
        credential_source=None,
        guidance=f"export {env_name}=…   # never commit the value",
    )


def build_ai_configuration_report(settings: CodestrataSettings) -> AiConfigurationReport:
    """Build a secret-free AI configuration report for CLI display."""

    supported = tuple(sorted(supported_assess_ai_providers()))
    active = (settings.ai.provider or "bedrock").strip().lower()
    bedrock = _bedrock_overview(settings)
    openai = _openai_overview(settings)
    providers = (bedrock, openai)

    checks: list[AiCheck] = []
    active_supported = active in supported
    if not active_supported:
        checks.append(
            AiCheck(
                label="Unsupported provider",
                ok=False,
                detail=(
                    f"Active [ai].provider={active!r} is not registered. "
                    f"Supported: {', '.join(supported)}"
                ),
                guidance="Set [ai].provider to bedrock or openai",
            )
        )
    else:
        checks.append(
            AiCheck(
                label=f"Active provider ({active})",
                ok=True,
                detail=f"[ai].provider = {active}",
            )
        )

    for overview in providers:
        label = "Bedrock" if overview.name == "bedrock" else "OpenAI"
        if overview.status is ConfigStatus.CONFIGURED:
            detail = overview.detail
            if overview.credential_source:
                detail = f"{detail} [source: {overview.credential_source}]"
            checks.append(AiCheck(label=f"{label} configured", ok=True, detail=detail))
            continue

        detail_lower = overview.detail.lower()
        if overview.name == "bedrock" and "unable to authenticate" in detail_lower:
            label_fail = "AWS authentication failed"
        elif overview.name == "bedrock" and (
            "credentials missing" in detail_lower
            or "profile not found" in detail_lower
            or "credential check failed" in detail_lower
        ):
            label_fail = "AWS credentials missing"
        elif overview.name == "openai" and "missing" in detail_lower:
            env_name = overview.required_env[0] if overview.required_env else "OPENAI_API_KEY"
            label_fail = f"{env_name} missing"
        else:
            label_fail = f"{label} not configured"
        checks.append(
            AiCheck(
                label=label_fail,
                ok=False,
                detail=overview.detail,
                guidance=overview.guidance,
            )
        )

    return AiConfigurationReport(
        active_provider=active,
        supported_providers=supported,
        active_supported=active_supported,
        providers=providers,
        checks=tuple(checks),
        model_id=_resolve_model_label(settings),
    )


__all__ = [
    "AiCheck",
    "AiConfigurationReport",
    "ConfigStatus",
    "ProviderOverview",
    "build_ai_configuration_report",
]
