"""Bridge Bedrock/AWS settings into contract configuration plus client inputs.

Two distinct shapes come out of this module:

* :class:`~codestrata.ai.provider_contracts.adapter_configuration.
  BedrockAdapterConfiguration` — the privacy-preserving Slice 11.3 value
  object used for diagnostics. It carries presence booleans only; the AWS
  profile name and region string are credential-adjacent and never leave
  this module.
* :class:`BedrockClientInputs` — the *private* values ``client.py`` needs to
  actually construct a Bedrock Runtime client.

**The AWS credential/profile/region precedence chain is not reimplemented
here.** ``client.py`` hands the explicit ``profile_name``/``region_name``
arguments and the settings object straight to
``codestrata.ai.aws_config.resolve_aws_config``, which owns the documented
precedence (explicit argument, then environment, then
``[aws]``/``[ai.bedrock]`` settings). Pre-resolving a settings value into the
explicit-argument slot here would silently promote settings above the
environment, so this module never does that.

The ``*_configured`` predicates below exist purely for diagnostics and for
rebuilding the legacy AWS guidance message; they deliberately do not read
``os.environ``, so "configured" means "named by an explicit argument or by
settings", never "resolvable from the ambient credential chain".
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.adapter_configuration import (
    BedrockAdapterConfiguration,
    build_bedrock_adapter_configuration,
)
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.config.settings import CodestrataSettings

# Named for documentation and diagnostics only. Reading these variables is
# ``aws_config``'s job, and this module never does it.
AWS_PROFILE_ENV_NAME = "AWS_PROFILE"
AWS_REGION_ENV_NAMES: tuple[str, ...] = ("AWS_REGION", "AWS_DEFAULT_REGION")


@dataclass(frozen=True, slots=True)
class BedrockClientInputs:
    """The private inputs required to construct a Bedrock Runtime client.

    ``__repr__`` is redacted: the AWS profile name and region are
    credential-adjacent deployment details and are never rendered, only
    their presence.
    """

    settings: CodestrataSettings | None
    profile_name: str | None
    region_name: str | None
    timeout_seconds: float

    @property
    def profile_configured(self) -> bool:
        """Whether an AWS profile is named by an explicit argument or by settings."""

        return _configured_profile_name(self.settings, self.profile_name) is not None

    @property
    def region_configured(self) -> bool:
        """Whether an AWS region is named by an explicit argument or by settings."""

        return _configured_region_name(self.settings, self.region_name) is not None

    @property
    def guidance_profile_name(self) -> str | None:
        """The profile name the legacy AWS guidance message interpolates, if any.

        Matches the pre-migration provider's ``self._profile_name or
        settings.aws.profile`` expression exactly.
        """

        return _configured_profile_name(self.settings, self.profile_name)

    def __repr__(self) -> str:
        return (
            "BedrockClientInputs("
            f"profile_configured={self.profile_configured}, "
            f"region_configured={self.region_configured}, "
            f"settings_present={self.settings is not None}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )


@dataclass(frozen=True, slots=True)
class BedrockRuntimeConfiguration:
    """Everything the adapter needs from configuration, split by privacy class.

    ``__repr__`` is redacted rather than inherited so that logging this
    object can never render an AWS profile name, a region, or the whole
    settings tree.
    """

    adapter_configuration: BedrockAdapterConfiguration
    client_inputs: BedrockClientInputs

    @property
    def profile_configured(self) -> bool:
        return self.client_inputs.profile_configured

    @property
    def region_configured(self) -> bool:
        return self.client_inputs.region_configured

    def __repr__(self) -> str:
        return f"BedrockRuntimeConfiguration(client_inputs={self.client_inputs!r})"

    def redacted(self) -> dict[str, object]:
        """Return a diagnostics-safe view (presence booleans and the timeout)."""

        view = dict(self.adapter_configuration.redacted())
        view["timeout_seconds"] = self.client_inputs.timeout_seconds
        return view


def _compact(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _configured_profile_name(
    settings: CodestrataSettings | None, explicit: str | None
) -> str | None:
    """Return the explicitly configured profile name, or ``None``.

    Diagnostics/guidance only — never used as the ``profile=`` argument to
    ``aws_config.resolve_aws_config``, which owns the real precedence.
    """

    from_settings = settings.aws.profile if settings is not None else None
    return _compact(explicit) or _compact(from_settings)


def _configured_region_name(
    settings: CodestrataSettings | None, explicit: str | None
) -> str | None:
    """Return the explicitly configured region name, or ``None``.

    Diagnostics only — never used as the ``region=`` argument to
    ``aws_config.resolve_aws_config``, which owns the real precedence.
    """

    from_settings = settings.aws.region if settings is not None else None
    legacy_from_settings = settings.ai.bedrock.region if settings is not None else None
    return _compact(explicit) or _compact(from_settings) or _compact(legacy_from_settings)


def resolve_configured_profile_name(
    *,
    settings: CodestrataSettings | None = None,
    profile_name: str | None = None,
) -> str | None:
    """Return the configured AWS profile name for diagnostics/guidance only."""

    return _configured_profile_name(settings, profile_name)


def resolve_configured_region_name(
    *,
    settings: CodestrataSettings | None = None,
    region_name: str | None = None,
) -> str | None:
    """Return the configured AWS region name for diagnostics only."""

    return _configured_region_name(settings, region_name)


def resolve_max_retries(settings: CodestrataSettings | None) -> int | None:
    """Return ``[ai.bedrock].max_retries`` purely so diagnostics can *represent* it.

    Carrying the value is not a claim that it is wired: the executor is
    pinned to ``maximum_attempts=1`` and the botocore client is pinned to
    ``max_attempts=1`` (CR-1). See ``engine/docs/ai-provider-bedrock.md``.
    """

    if settings is None:
        return None
    value = getattr(settings.ai.bedrock, "max_retries", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def build_runtime_configuration(
    *,
    settings: CodestrataSettings | None = None,
    profile_name: str | None = None,
    region_name: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> BedrockRuntimeConfiguration:
    """Project AWS/Bedrock settings into adapter configuration plus client inputs."""

    client_inputs = BedrockClientInputs(
        settings=settings,
        profile_name=_compact(profile_name),
        region_name=_compact(region_name),
        timeout_seconds=float(timeout_seconds),
    )
    adapter_configuration = build_bedrock_adapter_configuration(
        region_configured=client_inputs.region_configured,
        profile_configured=client_inputs.profile_configured,
        max_retries=resolve_max_retries(settings),
    )
    return BedrockRuntimeConfiguration(
        adapter_configuration=adapter_configuration,
        client_inputs=client_inputs,
    )


__all__ = [
    "AWS_PROFILE_ENV_NAME",
    "AWS_REGION_ENV_NAMES",
    "BedrockClientInputs",
    "BedrockRuntimeConfiguration",
    "build_runtime_configuration",
    "resolve_configured_profile_name",
    "resolve_configured_region_name",
    "resolve_max_retries",
]
