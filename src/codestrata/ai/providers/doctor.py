"""Assess AI provider configuration diagnostics (no secrets).

Used by ``codestrata ai`` / ``codestrata ai doctor``. Does not invoke models
or change assessment / enrichment behavior.

Bedrock checks use :func:`probe_aws_session_for_bedrock` — the same profile /
region / session resolution as Bedrock Runtime client creation.

OpenRouter checks (Epic 11, Slice 11.11) are local readiness only: dependency
import, API-key presence, required model presence, and HTTPS configuration
shape. They never construct an OpenRouter client, never send a prompt, and
never contact the provider.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from codestrata.ai.aws_config import probe_aws_session_for_bedrock
from codestrata.ai.providers.factory import (
    CODESTRATA_BEDROCK_MODEL_ID_ENV,
    CODESTRATA_OPENAI_MODEL_ID_ENV,
    CODESTRATA_OPENROUTER_MODEL_ID_ENV,
    supported_assess_ai_providers,
)
from codestrata.config.settings import DEFAULT_BEDROCK_MODEL_ID, CodestrataSettings

_MAX_OPENROUTER_APP_NAME_LENGTH = 128
_MAX_OPENROUTER_URL_LENGTH = 2048


class ConfigStatus(StrEnum):
    """Human-facing configuration status for a provider."""

    CONFIGURED = "Configured"
    NOT_CONFIGURED = "Not Configured"


class OpenRouterReadinessStatus(StrEnum):
    """Bounded OpenRouter local-readiness categories (Slice 11.11).

    These refine why OpenRouter is or is not ready without conflicting with
    :class:`ConfigStatus` used by all providers.
    """

    READY = "ready"
    NOT_SELECTED = "not_selected"
    MODEL_MISSING = "model_missing"
    CREDENTIAL_MISSING = "credential_missing"
    DEPENDENCY_MISSING = "dependency_missing"
    INVALID_CONFIGURATION = "invalid_configuration"
    NOT_CONFIGURED = "not_configured"


class OpenRouterBaseUrlStatus(StrEnum):
    """Bounded base-URL categories (never print the URL itself)."""

    DEFAULT = "default"
    CUSTOM_VALID = "custom_valid"
    INVALID = "invalid"


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
class OpenRouterDoctorReadiness:
    """Privacy-safe OpenRouter readiness facts for doctor and verification."""

    selected: bool
    readiness: OpenRouterReadinessStatus
    model_configured: bool
    credential_present: bool
    dependency_available: bool
    base_url_status: OpenRouterBaseUrlStatus
    site_url_configured: bool
    app_name_configured: bool
    detail: str
    guidance: str | None = None
    api_key_env_name: str = "OPENROUTER_API_KEY"

    @property
    def configured(self) -> bool:
        return self.readiness is OpenRouterReadinessStatus.READY

    def redacted(self) -> dict[str, object]:
        """Stable dict for verification — no secrets, URLs, models, or headers."""

        return {
            "app_name_configured": self.app_name_configured,
            "base_url_status": self.base_url_status.value,
            "configured": self.configured,
            "credential_present": self.credential_present,
            "credential_source": "environment",
            "dependency_available": self.dependency_available,
            "detail": self.detail,
            "guidance_present": bool(self.guidance),
            "model_configured": self.model_configured,
            "readiness": self.readiness.value,
            "selected": self.selected,
            "site_url_configured": self.site_url_configured,
        }


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
    openrouter_readiness: OpenRouterDoctorReadiness | None = None


def _environ(mapping: Mapping[str, str] | None) -> Mapping[str, str]:
    return mapping if mapping is not None else os.environ


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


def _openrouter_extra_installed() -> bool:
    """OpenRouter reuses the OpenAI-compatible optional extra."""

    return _openai_extra_installed()


def _openai_api_key_present(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    env_name = (settings.ai.openai.api_key_env or "OPENAI_API_KEY").strip() or "OPENAI_API_KEY"
    if _environ(environ).get(env_name, "").strip():
        return True, f"{env_name} is set (environment)"
    return False, f"{env_name} missing"


def _openrouter_api_key_env_name(settings: CodestrataSettings) -> str:
    return (settings.ai.openrouter.api_key_env or "OPENROUTER_API_KEY").strip() or (
        "OPENROUTER_API_KEY"
    )


def _openrouter_api_key_present(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    env_name = _openrouter_api_key_env_name(settings)
    return bool(_environ(environ).get(env_name, "").strip())


def _openrouter_model_configured(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    env_model = _environ(environ).get(CODESTRATA_OPENROUTER_MODEL_ID_ENV, "").strip()
    if env_model:
        return True
    return bool((settings.ai.openrouter.model or "").strip())


def _validate_https_url_shape(value: str) -> bool:
    compact = value.strip()
    if not compact or len(compact) > _MAX_OPENROUTER_URL_LENGTH:
        return False
    parsed = urlparse(compact)
    if parsed.scheme.lower() != "https":
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.query or parsed.fragment:
        return False
    if not parsed.netloc:
        return False
    return True


def _openrouter_base_url_status(settings: CodestrataSettings) -> OpenRouterBaseUrlStatus:
    configured = (settings.ai.openrouter.base_url or "").strip()
    if not configured:
        return OpenRouterBaseUrlStatus.DEFAULT
    if _validate_https_url_shape(configured):
        return OpenRouterBaseUrlStatus.CUSTOM_VALID
    return OpenRouterBaseUrlStatus.INVALID


def _openrouter_optional_headers_ok(settings: CodestrataSettings) -> tuple[bool, bool, bool]:
    """Return ``(ok, site_url_configured, app_name_configured)``."""

    site = (settings.ai.openrouter.site_url or "").strip()
    app = (settings.ai.openrouter.app_name or "").strip()
    site_configured = bool(site)
    app_configured = bool(app)
    if site and not _validate_https_url_shape(site):
        return False, site_configured, app_configured
    if app and len(app) > _MAX_OPENROUTER_APP_NAME_LENGTH:
        return False, site_configured, app_configured
    timeout = settings.ai.openrouter.timeout_seconds
    retries = settings.ai.openrouter.max_retries
    if timeout <= 0 or retries <= 0:
        return False, site_configured, app_configured
    return True, site_configured, app_configured


def evaluate_openrouter_readiness(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
    dependency_available: bool | None = None,
) -> OpenRouterDoctorReadiness:
    """Evaluate OpenRouter local readiness without network or client construction."""

    selected = (settings.ai.provider or "bedrock").strip().lower() == "openrouter"
    api_key_env_name = _openrouter_api_key_env_name(settings)
    dep_ok = (
        _openrouter_extra_installed()
        if dependency_available is None
        else bool(dependency_available)
    )
    model_ok = _openrouter_model_configured(settings, environ=environ)
    credential_ok = _openrouter_api_key_present(settings, environ=environ)
    base_status = _openrouter_base_url_status(settings)
    headers_ok, site_configured, app_configured = _openrouter_optional_headers_ok(settings)

    if not dep_ok:
        readiness = OpenRouterReadinessStatus.DEPENDENCY_MISSING
        detail = "client dependency unavailable (pip install 'codestrata[openai]')"
        guidance = "pip install 'codestrata[openai]'"
    elif base_status is OpenRouterBaseUrlStatus.INVALID or not headers_ok:
        readiness = OpenRouterReadinessStatus.INVALID_CONFIGURATION
        detail = "invalid OpenRouter configuration"
        guidance = (
            "Fix [ai.openrouter] base_url / site_url / app_name / timeout_seconds "
            "(HTTPS only; no credentials in URLs)"
        )
    elif not credential_ok:
        readiness = OpenRouterReadinessStatus.CREDENTIAL_MISSING
        detail = "API key not available (environment)"
        guidance = f"export {api_key_env_name}=…   # never commit the value"
    elif not model_ok:
        readiness = OpenRouterReadinessStatus.MODEL_MISSING
        detail = "model configuration missing"
        guidance = (
            "Set --model-id, CODESTRATA_OPENROUTER_MODEL_ID, or [ai.openrouter].model"
        )
    else:
        readiness = OpenRouterReadinessStatus.READY
        detail = "local readiness checks passed"
        guidance = None

    return OpenRouterDoctorReadiness(
        selected=selected,
        readiness=readiness,
        model_configured=model_ok,
        credential_present=credential_ok,
        dependency_available=dep_ok,
        base_url_status=base_status,
        site_url_configured=site_configured,
        app_name_configured=app_configured,
        detail=detail,
        guidance=guidance,
        api_key_env_name=api_key_env_name,
    )


def _resolve_model_label(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve a display label for the active provider.

    For OpenRouter the concrete model value is never returned — only a bounded
    presence label — so doctor / report serialization cannot leak it.
    """

    env = _environ(environ)
    provider = (settings.ai.provider or "bedrock").strip().lower()
    if provider == "openai":
        env_model = env.get(CODESTRATA_OPENAI_MODEL_ID_ENV, "").strip()
        if env_model:
            return env_model
        return (settings.ai.openai.answer_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
    if provider == "openrouter":
        if _openrouter_model_configured(settings, environ=environ):
            return "(configured)"
        return "(not configured)"
    env_model = env.get(CODESTRATA_BEDROCK_MODEL_ID_ENV, "").strip()
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


def _openai_overview(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> ProviderOverview:
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
    key_ok, key_detail = _openai_api_key_present(settings, environ=environ)
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


def _openrouter_overview(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
    dependency_available: bool | None = None,
) -> tuple[ProviderOverview, OpenRouterDoctorReadiness]:
    readiness = evaluate_openrouter_readiness(
        settings,
        environ=environ,
        dependency_available=dependency_available,
    )
    env_name = readiness.api_key_env_name
    required = (env_name,)
    optional = (CODESTRATA_OPENROUTER_MODEL_ID_ENV,)
    if readiness.configured:
        overview = ProviderOverview(
            name="openrouter",
            status=ConfigStatus.CONFIGURED,
            detail=readiness.detail,
            required_env=required,
            optional_env=optional,
            credential_source="environment",
        )
    else:
        overview = ProviderOverview(
            name="openrouter",
            status=ConfigStatus.NOT_CONFIGURED,
            detail=readiness.detail,
            required_env=required,
            optional_env=optional,
            credential_source="environment" if readiness.credential_present else None,
            guidance=readiness.guidance,
        )
    return overview, readiness


def _openrouter_check_label(readiness: OpenRouterDoctorReadiness) -> str:
    if readiness.readiness is OpenRouterReadinessStatus.READY:
        return "OpenRouter configured"
    if readiness.readiness is OpenRouterReadinessStatus.DEPENDENCY_MISSING:
        return "OpenRouter client dependency unavailable"
    if readiness.readiness is OpenRouterReadinessStatus.CREDENTIAL_MISSING:
        return "OpenRouter API key not available"
    if readiness.readiness is OpenRouterReadinessStatus.MODEL_MISSING:
        return "OpenRouter model configuration missing"
    if readiness.readiness is OpenRouterReadinessStatus.INVALID_CONFIGURATION:
        return "OpenRouter invalid configuration"
    return "OpenRouter not configured"


def build_ai_configuration_report(
    settings: CodestrataSettings,
    *,
    environ: Mapping[str, str] | None = None,
    openrouter_dependency_available: bool | None = None,
) -> AiConfigurationReport:
    """Build a secret-free AI configuration report for CLI display."""

    supported = tuple(sorted(supported_assess_ai_providers()))
    active = (settings.ai.provider or "bedrock").strip().lower()
    bedrock = _bedrock_overview(settings)
    openai = _openai_overview(settings, environ=environ)
    openrouter, openrouter_readiness = _openrouter_overview(
        settings,
        environ=environ,
        dependency_available=openrouter_dependency_available,
    )
    providers = (bedrock, openai, openrouter)

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
                guidance="Set [ai].provider to bedrock, openai, or openrouter",
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
        if overview.name == "bedrock":
            label = "Bedrock"
        elif overview.name == "openai":
            label = "OpenAI"
        else:
            label = "OpenRouter"

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
        elif overview.name == "openrouter":
            label_fail = _openrouter_check_label(openrouter_readiness)
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
        model_id=_resolve_model_label(settings, environ=environ),
        openrouter_readiness=openrouter_readiness,
    )


__all__ = [
    "AiCheck",
    "AiConfigurationReport",
    "ConfigStatus",
    "OpenRouterBaseUrlStatus",
    "OpenRouterDoctorReadiness",
    "OpenRouterReadinessStatus",
    "ProviderOverview",
    "build_ai_configuration_report",
    "evaluate_openrouter_readiness",
]
