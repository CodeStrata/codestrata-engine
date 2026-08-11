"""Execution profiles for CodeStrata configuration (Phase 5.20).

Profiles supply secure defaults only. Precedence is:

    CLI > environment variables > configuration file > profile defaults

Secrets (API keys, connection strings, AWS credential material) are never
stored in profile defaults and must never appear in effective-settings dumps.
"""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

PROFILE_ENV_VAR = "CODESTRATA_PROFILE"
BEDROCK_MODEL_ENV_VAR = "CODESTRATA_BEDROCK_MODEL_ID"
OPENAI_API_KEY_ENV_OVERRIDE = "CODESTRATA_OPENAI_API_KEY_ENV"
OPENROUTER_MODEL_ENV_VAR = "CODESTRATA_OPENROUTER_MODEL_ID"

ProfileSource = Literal["cli", "environment", "configuration", "default"]


class ExecutionProfile(StrEnum):
    """Named execution profiles."""

    COMMUNITY = "community"
    LOCAL = "local"
    ENTERPRISE = "enterprise"
    BEDROCK = "bedrock"
    OPENAI = "openai"


ALLOWED_PROFILES: frozenset[str] = frozenset(item.value for item in ExecutionProfile)
DEFAULT_PROFILE = ExecutionProfile.COMMUNITY.value


def profile_defaults(profile: str) -> dict[str, Any]:
    """Return secure default overlays for ``profile`` (never includes secrets)."""

    name = normalize_profile_name(profile)
    shared_local_ai = {
        "provider": "bedrock",
        "embedding_provider": "deterministic",
        "answer_provider": "deterministic_extractive",
    }
    if name == ExecutionProfile.COMMUNITY:
        return {
            "profile": name,
            "enterprise": {"enabled": False},
            "ai": dict(shared_local_ai),
        }
    if name == ExecutionProfile.LOCAL:
        return {
            "profile": name,
            "enterprise": {"enabled": False},
            "ai": dict(shared_local_ai),
        }
    if name == ExecutionProfile.ENTERPRISE:
        return {
            "profile": name,
            "enterprise": {"enabled": True},
            "ai": dict(shared_local_ai),
        }
    if name == ExecutionProfile.BEDROCK:
        return {
            "profile": name,
            "enterprise": {"enabled": False},
            "ai": {
                "provider": "bedrock",
                "embedding_provider": "bedrock",
                "answer_provider": "bedrock",
            },
            "aws": {},
        }
    # openai
    return {
        "profile": name,
        "enterprise": {"enabled": False},
        "ai": {
            # Assessment Converse remains Bedrock-backed today; knowledge uses OpenAI.
            "provider": "bedrock",
            "embedding_provider": "openai",
            "answer_provider": "openai",
            "openai": {
                "api_key_env": "OPENAI_API_KEY",
            },
        },
    }


def normalize_profile_name(value: str | None) -> str:
    """Normalize and validate a profile name."""

    compact = str(value or "").strip().lower()
    if not compact:
        raise ConfigurationProfileError(
            "Execution profile is empty.\n\n"
            f"Fix: set profile to one of {sorted(ALLOWED_PROFILES)} via "
            f"--profile, {PROFILE_ENV_VAR}, or profile = \"...\" in codestrata.toml"
        )
    if compact not in ALLOWED_PROFILES:
        raise ConfigurationProfileError(
            f"Unknown execution profile {compact!r}.\n\n"
            f"Fix: choose one of {sorted(ALLOWED_PROFILES)}"
        )
    return compact


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` onto ``base`` without mutating inputs."""

    result: dict[str, Any] = deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def resolve_profile_name(
    *,
    cli_profile: str | None = None,
    config_data: dict[str, Any] | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[str, ProfileSource]:
    """Resolve active profile name and its precedence source."""

    env = environ if environ is not None else dict(os.environ)
    if cli_profile is not None and str(cli_profile).strip():
        return normalize_profile_name(cli_profile), "cli"
    env_value = str(env.get(PROFILE_ENV_VAR, "") or "").strip()
    if env_value:
        return normalize_profile_name(env_value), "environment"
    raw = config_data or {}
    file_value = raw.get("profile")
    if file_value is None and isinstance(raw.get("execution"), dict):
        file_value = raw["execution"].get("profile")
    if file_value is not None and str(file_value).strip():
        return normalize_profile_name(str(file_value)), "configuration"
    return DEFAULT_PROFILE, "default"


def apply_environment_overlays(
    data: dict[str, Any],
    *,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Apply known CodeStrata environment overlays (env wins over TOML values).

    AWS_PROFILE / AWS_REGION are intentionally not copied into settings here;
    ``resolve_aws_config`` resolves them with Phase 5.20 precedence so source
    attribution stays accurate.
    """

    env = environ if environ is not None else dict(os.environ)
    out = deepcopy(data)

    bedrock_model = str(env.get(BEDROCK_MODEL_ENV_VAR, "") or "").strip()
    if bedrock_model:
        out.setdefault("ai", {})
        out["ai"].setdefault("bedrock", {})
        out["ai"]["bedrock"]["model_id"] = bedrock_model

    openai_env_name = str(env.get(OPENAI_API_KEY_ENV_OVERRIDE, "") or "").strip()
    if openai_env_name:
        out.setdefault("ai", {})
        out["ai"].setdefault("openai", {})
        out["ai"]["openai"]["api_key_env"] = openai_env_name

    openrouter_model = str(env.get(OPENROUTER_MODEL_ENV_VAR, "") or "").strip()
    if openrouter_model:
        out.setdefault("ai", {})
        out["ai"].setdefault("openrouter", {})
        out["ai"]["openrouter"]["model"] = openrouter_model

    platform_enabled = str(env.get("CODESTRATA_PLATFORM_ENABLED", "") or "").strip().lower()
    if platform_enabled in {"1", "true", "yes", "on"}:
        out.setdefault("platform", {})
        out["platform"]["enabled"] = True
    elif platform_enabled in {"0", "false", "no", "off"}:
        out.setdefault("platform", {})
        out["platform"]["enabled"] = False

    platform_url = str(env.get("CODESTRATA_PLATFORM_URL", "") or "").strip()
    if platform_url:
        out.setdefault("platform", {})
        out["platform"]["base_url"] = platform_url

    platform_org = str(env.get("CODESTRATA_PLATFORM_ORGANIZATION_ID", "") or "").strip()
    if platform_org:
        out.setdefault("platform", {})
        out["platform"]["organization_id"] = platform_org

    platform_ws = str(env.get("CODESTRATA_PLATFORM_WORKSPACE_ID", "") or "").strip()
    if platform_ws:
        out.setdefault("platform", {})
        out["platform"]["workspace_id"] = platform_ws

    return out


def merge_profile_configuration(
    config_data: dict[str, Any],
    *,
    cli_profile: str | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str, ProfileSource]:
    """Merge profile defaults, TOML, and environment into one settings dict."""

    profile, source = resolve_profile_name(
        cli_profile=cli_profile,
        config_data=config_data,
        environ=environ,
    )
    # TOML may use [execution].profile; normalize to top-level profile field.
    cleaned = deepcopy(config_data)
    execution = cleaned.pop("execution", None)
    if isinstance(execution, dict):
        # Preserve non-profile execution keys if added later; drop profile alias.
        leftover = {key: value for key, value in execution.items() if key != "profile"}
        if leftover:
            cleaned["execution"] = leftover
    merged = deep_merge(profile_defaults(profile), cleaned)
    merged["profile"] = profile
    merged = apply_environment_overlays(merged, environ=environ)
    merged["profile"] = profile
    return merged, profile, source


@dataclass(frozen=True)
class ConfigurationIssue:
    """Actionable configuration validation issue."""

    code: str
    message: str
    severity: Literal["error", "warning"] = "error"

    def format(self) -> str:
        return f"[{self.severity}] {self.message}"


class ConfigurationProfileError(ValueError):
    """Raised when profile resolution or validation fails."""

    def __init__(self, message: str, *, issues: tuple[ConfigurationIssue, ...] = ()) -> None:
        super().__init__(message)
        self.issues = issues


def _is_deterministic_provider(name: str) -> bool:
    return name.strip().lower().startswith("deterministic")


def _resolved_bedrock_region(
    settings_like: Any,
    *,
    environ: dict[str, str] | None = None,
) -> str | None:
    env = environ if environ is not None else dict(os.environ)
    aws_region = getattr(getattr(settings_like, "aws", None), "region", None)
    bedrock = getattr(getattr(settings_like, "ai", None), "bedrock", None)
    bed_region = getattr(bedrock, "region", None)
    for candidate in (
        aws_region,
        bed_region,
        env.get("AWS_REGION"),
        env.get("AWS_DEFAULT_REGION"),
    ):
        compact = str(candidate or "").strip()
        if compact:
            return compact
    return None


def validate_profile_settings(
    settings: Any,
    *,
    profile: str | None = None,
    profile_source: ProfileSource | None = None,
    strict: bool = False,
    environ: dict[str, str] | None = None,
) -> list[ConfigurationIssue]:
    """Validate effective settings against the active execution profile."""

    del profile_source  # reserved for richer diagnostics
    env = environ if environ is not None else dict(os.environ)
    name = normalize_profile_name(profile or getattr(settings, "profile", DEFAULT_PROFILE))
    issues: list[ConfigurationIssue] = []
    ai = settings.ai
    embedding = str(ai.embedding_provider)
    answer = str(ai.answer_provider)
    assessment = str(ai.provider)
    enterprise_enabled = bool(settings.enterprise.enabled)

    if name == ExecutionProfile.LOCAL:
        if not _is_deterministic_provider(embedding):
            issues.append(
                ConfigurationIssue(
                    code="local_external_embedding",
                    message=(
                        f"Profile 'local' requires a deterministic embedding provider, "
                        f"got {embedding!r}.\n"
                        "Fix: set [ai].embedding_provider = \"deterministic\" "
                        "or switch profile (for example profile = \"bedrock\")."
                    ),
                )
            )
        if not _is_deterministic_provider(answer):
            issues.append(
                ConfigurationIssue(
                    code="local_external_answer",
                    message=(
                        f"Profile 'local' requires a deterministic answer provider, "
                        f"got {answer!r}.\n"
                        "Fix: set [ai].answer_provider = \"deterministic_extractive\" "
                        "or switch profile."
                    ),
                )
            )
        if assessment == "openai":
            issues.append(
                ConfigurationIssue(
                    code="local_external_assessment",
                    message=(
                        "Profile 'local' cannot use OpenAI for assessment enrichment.\n"
                        "Fix: use profile = \"openai\" for OpenAI knowledge providers, "
                        "or keep local/deterministic assessment (omit --with-ai)."
                    ),
                )
            )

    if name == ExecutionProfile.COMMUNITY:
        if not _is_deterministic_provider(embedding) or not _is_deterministic_provider(
            answer
        ):
            issues.append(
                ConfigurationIssue(
                    code="community_external_ai",
                    message=(
                        "Community profile is using external AI providers. "
                        "Prefer profile = \"bedrock\" or profile = \"openai\" "
                        "when enabling production providers."
                    ),
                    severity="warning",
                )
            )

    if name == ExecutionProfile.ENTERPRISE and not enterprise_enabled:
        issues.append(
            ConfigurationIssue(
                code="enterprise_disabled",
                message=(
                    "Profile 'enterprise' requires [enterprise].enabled = true.\n"
                    "Fix: enable enterprise in codestrata.toml or choose profile = "
                    "\"community\" / \"local\"."
                ),
            )
        )

    if name == ExecutionProfile.BEDROCK:
        if assessment != "bedrock":
            issues.append(
                ConfigurationIssue(
                    code="bedrock_assessment_provider",
                    message=(
                        f"Profile 'bedrock' requires [ai].provider = \"bedrock\", "
                        f"got {assessment!r}."
                    ),
                )
            )
        if embedding not in {"bedrock", "deterministic"}:
            issues.append(
                ConfigurationIssue(
                    code="bedrock_embedding_provider",
                    message=(
                        f"Profile 'bedrock' expects embedding_provider "
                        f"\"bedrock\" (or deterministic), got {embedding!r}."
                    ),
                )
            )
        if answer not in {"bedrock", "deterministic", "deterministic_extractive"}:
            issues.append(
                ConfigurationIssue(
                    code="bedrock_answer_provider",
                    message=(
                        f"Profile 'bedrock' expects answer_provider "
                        f"\"bedrock\" (or deterministic), got {answer!r}."
                    ),
                )
            )
        if _resolved_bedrock_region(settings, environ=env) is None:
            issues.append(
                ConfigurationIssue(
                    code="bedrock_region_missing",
                    message=(
                        "Profile 'bedrock' requires an AWS region.\n"
                        "Fix: set [aws].region or [ai.bedrock].region in codestrata.toml, "
                        "or export AWS_REGION / AWS_DEFAULT_REGION."
                    ),
                )
            )

    if name == ExecutionProfile.OPENAI:
        if embedding != "openai":
            issues.append(
                ConfigurationIssue(
                    code="openai_embedding_provider",
                    message=(
                        f"Profile 'openai' requires [ai].embedding_provider = \"openai\", "
                        f"got {embedding!r}."
                    ),
                )
            )
        if answer != "openai":
            issues.append(
                ConfigurationIssue(
                    code="openai_answer_provider",
                    message=(
                        f"Profile 'openai' requires [ai].answer_provider = \"openai\", "
                        f"got {answer!r}."
                    ),
                )
            )
        api_key_env = str(ai.openai.api_key_env or "").strip()
        if not api_key_env:
            issues.append(
                ConfigurationIssue(
                    code="openai_api_key_env_missing",
                    message=(
                        "Profile 'openai' requires [ai.openai].api_key_env "
                        "(environment variable *name*, not the secret).\n"
                        "Fix: api_key_env = \"OPENAI_API_KEY\""
                    ),
                )
            )
        elif strict and not str(env.get(api_key_env, "") or "").strip():
            issues.append(
                ConfigurationIssue(
                    code="openai_api_key_absent",
                    message=(
                        f"Environment variable {api_key_env!r} is not set.\n"
                        f"Fix: export {api_key_env}=... (value is never written to "
                        "logs, reports, or config dumps) or use profile = \"local\"."
                    ),
                )
            )

    # Community may enable enterprise via configuration; that is intentional.
    if name == ExecutionProfile.COMMUNITY and enterprise_enabled:
        issues.append(
            ConfigurationIssue(
                code="community_enterprise_enabled",
                message=(
                    "Community profile with [enterprise].enabled = true. "
                    "Platform Engineering Knowledge Graph features are active. "
                    "Prefer profile = \"enterprise\" for clarity "
                    "(CodeStrata Platform capability)."
                ),
                severity="warning",
            )
        )

    if strict and name == ExecutionProfile.BEDROCK:
        # Soft presence check only — never inspect secret material.
        has_key = bool(
            str(env.get("AWS_ACCESS_KEY_ID", "") or "").strip()
            or str(env.get("AWS_PROFILE", "") or "").strip()
            or str(getattr(settings.aws, "profile", None) or "").strip()
        )
        if not has_key:
            issues.append(
                ConfigurationIssue(
                    code="bedrock_credentials_hint",
                    message=(
                        "No AWS_PROFILE / aws.profile / AWS_ACCESS_KEY_ID detected for "
                        "Bedrock. Runtime uses the default AWS credentials chain.\n"
                        "Fix: configure an AWS profile or credentials before "
                        "assess --with-ai / Bedrock knowledge providers."
                    ),
                    severity="warning",
                )
            )

    return issues


def raise_on_errors(issues: list[ConfigurationIssue]) -> None:
    """Raise when any error-severity issues are present."""

    errors = [item for item in issues if item.severity == "error"]
    if not errors:
        return
    body = "\n\n".join(item.format() for item in errors)
    raise ConfigurationProfileError(
        f"Invalid execution profile configuration:\n\n{body}",
        issues=tuple(issues),
    )


__all__ = [
    "ALLOWED_PROFILES",
    "BEDROCK_MODEL_ENV_VAR",
    "ConfigurationIssue",
    "ConfigurationProfileError",
    "DEFAULT_PROFILE",
    "ExecutionProfile",
    "OPENAI_API_KEY_ENV_OVERRIDE",
    "OPENROUTER_MODEL_ENV_VAR",
    "PROFILE_ENV_VAR",
    "ProfileSource",
    "apply_environment_overlays",
    "deep_merge",
    "merge_profile_configuration",
    "normalize_profile_name",
    "profile_defaults",
    "raise_on_errors",
    "resolve_profile_name",
    "validate_profile_settings",
]
