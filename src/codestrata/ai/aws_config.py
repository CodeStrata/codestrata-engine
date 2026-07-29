"""Centralized AWS session and Bedrock Runtime client configuration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol, cast

from codestrata.config.settings import CodestrataSettings

logger = logging.getLogger(__name__)

AWS_PROFILE_ENV = "AWS_PROFILE"
AWS_REGION_ENV = "AWS_REGION"
AWS_DEFAULT_REGION_ENV = "AWS_DEFAULT_REGION"


class BedrockRuntimeClient(Protocol):
    """Minimal Bedrock Runtime client protocol for dependency injection."""

    def converse(self, **kwargs: Any) -> Any:
        """Invoke a Bedrock model via the Converse API."""


@dataclass(frozen=True, slots=True)
class ResolvedAwsConfig:
    """Resolved AWS profile and region for session construction."""

    profile: str | None
    region: str | None
    source_profile: str
    source_region: str


@dataclass(frozen=True, slots=True)
class AwsSessionProbe:
    """Secret-free probe of the same AWS session Bedrock runtime would build."""

    ok: bool
    resolved: ResolvedAwsConfig
    effective_region: str | None
    credential_source: str
    detail: str
    guidance: str | None = None


def resolve_aws_config(
    *,
    settings: CodestrataSettings | None = None,
    profile: str | None = None,
    region: str | None = None,
) -> ResolvedAwsConfig:
    """Resolve AWS profile/region from explicit args, environment, then settings.

    Precedence for profile:
    1. Explicit ``profile`` argument
    2. ``AWS_PROFILE`` environment variable
    3. ``[aws].profile`` from CodeStrata settings (optional override only)
    4. ``None`` (boto3 default credential chain)

    Precedence for region:
    1. Explicit ``region`` argument
    2. ``AWS_REGION`` / ``AWS_DEFAULT_REGION``
    3. ``[aws].region`` from CodeStrata settings
    4. ``ai.bedrock.region`` from CodeStrata settings (legacy)
    5. ``None`` (boto3 default region chain / shared config)

    Community Edition does not require a repository-local AWS profile. Prefer
    ``AWS_PROFILE`` / the default credential chain on each machine.
    """

    resolved_profile, profile_source = _first_nonempty(
        (profile, "argument"),
        (os.environ.get(AWS_PROFILE_ENV), f"environment {AWS_PROFILE_ENV}"),
        (_settings_aws_profile(settings), "codestrata.toml [aws].profile"),
    )
    if resolved_profile is None:
        profile_source = "boto3 default credential chain"

    resolved_region, region_source = _first_nonempty(
        (region, "argument"),
        (os.environ.get(AWS_REGION_ENV), f"environment {AWS_REGION_ENV}"),
        (
            os.environ.get(AWS_DEFAULT_REGION_ENV),
            f"environment {AWS_DEFAULT_REGION_ENV}",
        ),
        (_settings_aws_region(settings), "codestrata.toml [aws].region"),
        (_settings_bedrock_region(settings), "codestrata.toml [ai.bedrock].region"),
    )
    if resolved_region is None:
        region_source = "boto3 default region chain"

    return ResolvedAwsConfig(
        profile=resolved_profile,
        region=resolved_region,
        source_profile=profile_source,
        source_region=region_source,
    )


def build_boto3_session(resolved: ResolvedAwsConfig) -> Any:
    """Build a boto3 Session the same way Bedrock Runtime client creation does."""

    try:
        import boto3
        from botocore.exceptions import ProfileNotFound
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("boto3 is required to create a Bedrock Runtime client") from error

    session_kwargs: dict[str, Any] = {}
    if resolved.profile:
        session_kwargs["profile_name"] = resolved.profile
    if resolved.region:
        session_kwargs["region_name"] = resolved.region

    try:
        return boto3.Session(**session_kwargs)
    except ProfileNotFound as error:
        raise AwsAuthenticationError(
            format_aws_authentication_error(profile=resolved.profile)
        ) from error
    except Exception as error:  # noqa: BLE001 - AWS boundary
        if _looks_like_auth_failure(error):
            raise AwsAuthenticationError(
                format_aws_authentication_error(profile=resolved.profile)
            ) from error
        raise


def probe_aws_session_for_bedrock(
    *,
    settings: CodestrataSettings | None = None,
    profile: str | None = None,
    region: str | None = None,
) -> AwsSessionProbe:
    """Probe AWS credentials/region exactly as Bedrock runtime resolution would.

    Never returns secret values.
    """

    resolved = resolve_aws_config(settings=settings, profile=profile, region=region)
    credential_source = _describe_credential_source(resolved)

    try:
        session = build_boto3_session(resolved)
    except AwsAuthenticationError as error:
        return AwsSessionProbe(
            ok=False,
            resolved=resolved,
            effective_region=resolved.region,
            credential_source=credential_source,
            detail=str(error).split("\n", 1)[0],
            guidance=format_aws_authentication_error(profile=resolved.profile),
        )
    except RuntimeError as error:
        return AwsSessionProbe(
            ok=False,
            resolved=resolved,
            effective_region=resolved.region,
            credential_source=credential_source,
            detail=str(error),
            guidance="Install the Bedrock extra: pip install 'codestrata[bedrock]'",
        )

    effective_region = resolved.region or getattr(session, "region_name", None)
    region_source = resolved.source_region
    if resolved.region is None and effective_region:
        region_source = "boto3 default region chain"

    try:
        credentials = session.get_credentials()
    except Exception as error:  # noqa: BLE001
        return AwsSessionProbe(
            ok=False,
            resolved=resolved,
            effective_region=effective_region,
            credential_source=credential_source,
            detail=f"AWS credential check failed ({type(error).__name__})",
            guidance=format_aws_authentication_error(profile=resolved.profile),
        )

    if credentials is None:
        return AwsSessionProbe(
            ok=False,
            resolved=resolved,
            effective_region=effective_region,
            credential_source=credential_source,
            detail="AWS credentials missing",
            guidance=format_aws_authentication_error(profile=resolved.profile),
        )

    if not effective_region:
        return AwsSessionProbe(
            ok=False,
            resolved=resolved,
            effective_region=None,
            credential_source=credential_source,
            detail=(
                "AWS region missing (set AWS_REGION, [aws].region, "
                "or [ai.bedrock].region)"
            ),
            guidance=(
                "export AWS_REGION=us-east-1\n"
                "# or add region = \"us-east-1\" under [aws] in codestrata.toml"
            ),
        )

    # Validate credentials are usable (expired SSO / invalid tokens fail here).
    # Doctor must not report "Configured" when assess --with-ai would auth-fail.
    try:
        sts = session.client("sts", region_name=effective_region)
        sts.get_caller_identity()
    except Exception as error:  # noqa: BLE001 - AWS boundary
        detail = (
            "Unable to authenticate with AWS "
            f"({type(error).__name__}). Credentials may be expired or invalid."
        )
        return AwsSessionProbe(
            ok=False,
            resolved=resolved,
            effective_region=effective_region,
            credential_source=credential_source,
            detail=detail,
            guidance=format_aws_authentication_error(profile=resolved.profile),
        )

    detail = (
        f"credentials via {credential_source}; "
        f"region={effective_region} ({region_source})"
    )
    return AwsSessionProbe(
        ok=True,
        resolved=resolved,
        effective_region=effective_region,
        credential_source=credential_source,
        detail=detail,
        guidance=None,
    )


def create_bedrock_runtime_client(
    *,
    settings: CodestrataSettings | None = None,
    profile: str | None = None,
    region: str | None = None,
    timeout_seconds: float = 60.0,
    model_id: str | None = None,
) -> BedrockRuntimeClient:
    """Create the single shared Bedrock Runtime client used by CodeStrata.

    Never hardcodes credentials. Uses the standard AWS credential provider chain:
    optional ``AWS_PROFILE`` / ``[aws].profile``, else default chain; region from
    env or optional config.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    resolved = resolve_aws_config(settings=settings, profile=profile, region=region)
    _log_aws_session(resolved, model_id=model_id)

    try:
        from botocore.config import Config
    except ImportError as error:  # pragma: no cover - exercised when boto3 missing
        raise RuntimeError("boto3 is required to create a Bedrock Runtime client") from error

    read_timeout = max(1, int(timeout_seconds))
    connect_timeout = min(10, read_timeout)
    config = Config(
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        retries={"max_attempts": 1, "mode": "standard"},
    )

    session = build_boto3_session(resolved)

    client_kwargs: dict[str, Any] = {"config": config}
    if resolved.region:
        client_kwargs["region_name"] = resolved.region

    try:
        client = session.client("bedrock-runtime", **client_kwargs)
    except Exception as error:  # noqa: BLE001 - AWS boundary
        if _looks_like_auth_failure(error):
            raise AwsAuthenticationError(
                format_aws_authentication_error(profile=resolved.profile)
            ) from error
        raise

    return cast(BedrockRuntimeClient, client)


class AwsAuthenticationError(RuntimeError):
    """Raised when AWS authentication/profile resolution fails."""


def format_aws_authentication_error(*, profile: str | None = None) -> str:
    """Return actionable AWS authentication guidance (no secrets)."""

    profile_label = profile.strip() if profile and profile.strip() else "<your-profile>"
    return (
        "Unable to authenticate with AWS.\n"
        "\n"
        "CodeStrata uses the standard AWS credential provider chain. "
        "Prefer machine-local credentials (AWS_PROFILE or default chain); "
        "do not commit developer-specific [aws].profile values.\n"
        "\n"
        "Try one of:\n"
        "\n"
        f"- export AWS_PROFILE={profile_label} && aws sso login --profile {profile_label}\n"
        "- export AWS_PROFILE=<your-profile>   # named profile on this machine\n"
        "- aws configure   # default profile / access keys\n"
        "- export AWS_ACCESS_KEY_ID=… and AWS_SECRET_ACCESS_KEY=…\n"
        "- export AWS_REGION=us-east-1   # required for Bedrock\n"
        "- If codestrata.toml sets [aws].profile to a missing name, remove it "
        "and use AWS_PROFILE instead"
    )


def _describe_credential_source(resolved: ResolvedAwsConfig) -> str:
    """Human-readable credential source label (never includes secret values)."""

    if resolved.profile:
        return f"profile {resolved.profile!r} ({resolved.source_profile})"
    if os.environ.get("AWS_ACCESS_KEY_ID", "").strip():
        return "environment AWS_ACCESS_KEY_ID (default chain)"
    if os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "").strip() or os.environ.get(
        "AWS_CONTAINER_CREDENTIALS_FULL_URI", ""
    ).strip():
        return "container credential provider (default chain)"
    if os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE", "").strip():
        return "web identity token (default chain)"
    return "boto3 default credential chain"


def _settings_aws_profile(settings: CodestrataSettings | None) -> str | None:
    if settings is None:
        return None
    return settings.aws.profile


def _settings_aws_region(settings: CodestrataSettings | None) -> str | None:
    if settings is None:
        return None
    return settings.aws.region


def _settings_bedrock_region(settings: CodestrataSettings | None) -> str | None:
    if settings is None:
        return None
    return settings.ai.bedrock.region


def _first_nonempty(
    *candidates: tuple[str | None, str],
) -> tuple[str | None, str]:
    for value, source in candidates:
        if value is None:
            continue
        compact = value.strip()
        if compact:
            return compact, source
    return None, "unset"


def _log_aws_session(resolved: ResolvedAwsConfig, *, model_id: str | None) -> None:
    profile_display = resolved.profile or "(default credential chain)"
    region_display = resolved.region or "(boto3 default)"
    model_display = model_id.strip() if model_id and model_id.strip() else "(not set)"
    logger.info(
        "AWS session for Bedrock: profile=%s region=%s model_id=%s "
        "(profile_source=%s, region_source=%s)",
        profile_display,
        region_display,
        model_display,
        resolved.source_profile,
        resolved.source_region,
    )


def _looks_like_auth_failure(error: Exception) -> bool:
    name = type(error).__name__
    if name in {
        "ProfileNotFound",
        "NoCredentialsError",
        "PartialCredentialsError",
        "TokenRetrievalError",
        "UnauthorizedSSOTokenError",
        "SSOTokenLoadError",
    }:
        return True
    code = _client_error_code(error)
    if code in {
        "UnrecognizedClientException",
        "InvalidSignatureException",
        "ExpiredTokenException",
        "AuthFailure",
        "AccessDeniedException",
        "UnauthorizedOperation",
    }:
        return True
    message = str(error).lower()
    return any(
        token in message
        for token in (
            "unable to locate credentials",
            "expired token",
            "invalid security token",
            "not authorized",
            "sso",
            "authentication",
        )
    )


def _client_error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    error_payload = response.get("Error")
    if not isinstance(error_payload, dict):
        return None
    code = error_payload.get("Code")
    return str(code) if code is not None else None


__all__ = [
    "AWS_DEFAULT_REGION_ENV",
    "AWS_PROFILE_ENV",
    "AWS_REGION_ENV",
    "AwsAuthenticationError",
    "AwsSessionProbe",
    "BedrockRuntimeClient",
    "ResolvedAwsConfig",
    "build_boto3_session",
    "create_bedrock_runtime_client",
    "format_aws_authentication_error",
    "probe_aws_session_for_bedrock",
    "resolve_aws_config",
]
