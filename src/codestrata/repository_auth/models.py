"""Provider-neutral repository authentication models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator, model_validator


class AuthenticationProviderType(StrEnum):
    """Configured credential provider kinds."""

    NONE = "none"
    GITHUB_TOKEN = "github_token"
    SSH_AGENT = "ssh_agent"


class AuthenticationMethod(StrEnum):
    """How credentials are presented to Git at runtime."""

    NONE = "none"
    HTTPS_ASKPASS = "https_askpass"
    SSH_AGENT = "ssh_agent"


_ENV_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


class RepositoryAuthenticationConfig(BaseModel):
    """Credential reference configuration (never contains secret values)."""

    model_config = ConfigDict(extra="forbid")

    type: AuthenticationProviderType
    token_env: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("token_env")
    @classmethod
    def validate_token_env(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.strip()
        if not compact:
            raise ValueError("token_env must be a nonempty environment-variable name")
        import re

        if re.fullmatch(_ENV_NAME_PATTERN, compact) is None:
            raise ValueError(
                "token_env must be a valid environment-variable name "
                "(letters, digits, and underscore; must not start with a digit)"
            )
        return compact

    @model_validator(mode="after")
    def validate_type_requirements(self) -> RepositoryAuthenticationConfig:
        if self.type is AuthenticationProviderType.GITHUB_TOKEN:
            if self.token_env is None:
                raise ValueError("token_env is required when type is github_token")
        elif self.token_env is not None:
            raise ValueError("token_env is only valid when type is github_token")
        if self.type is AuthenticationProviderType.NONE:
            raise ValueError(
                "authentication type 'none' is represented by omitting repository.authentication"
            )
        return self


class SanitizedAuthenticationMetadata(BaseModel):
    """Non-secret authentication metadata safe for diagnostics."""

    provider_id: str
    method: AuthenticationMethod
    authenticated: bool = False


@dataclass
class ResolvedRepositoryCredential:
    """Runtime-only credential. Never serialize or include in domain models."""

    provider_id: str
    method: AuthenticationMethod
    secret: SecretStr | None = field(default=None, repr=False)
    username: str | None = field(default=None, repr=False)

    def get_secret_value(self) -> str | None:
        """Return the secret string for scoped Git execution only."""

        if self.secret is None:
            return None
        return self.secret.get_secret_value()

    def __repr__(self) -> str:
        return (
            "ResolvedRepositoryCredential("
            f"provider_id={self.provider_id!r}, "
            f"method={self.method!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def to_public_dict(self) -> dict[str, Any]:
        """Return only non-secret metadata."""

        return {
            "provider_id": self.provider_id,
            "method": self.method.value,
            "authenticated": self.secret is not None
            or self.method is AuthenticationMethod.SSH_AGENT,
        }


# Fixed non-secret username accepted by GitHub HTTPS token auth.
GITHUB_HTTPS_TOKEN_USERNAME = "x-access-token"

# Child-process-only environment keys for askpass helpers.
ASKPASS_USERNAME_ENV = "CODESTRATA_GIT_ASKPASS_USERNAME"
ASKPASS_PASSWORD_ENV = "CODESTRATA_GIT_ASKPASS_PASSWORD"
