"""Security-relevant configuration key matching (literal collection only)."""

from __future__ import annotations

import re

from codestrata.domain.evidence.repository_sensitive.enums import ConfigurationKeyFamily

# Tokenized key fragments (matched on underscore-normalized keys).
_SENSITIVE_TOKENS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "private_key",
        "client_secret",
        "credential",
        "credentials",
        "connection_string",
        "jdbc",
    }
)

_SECRET_TOKENS = frozenset(
    {
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "client_secret",
        "private_key",
    }
)

_CREDENTIAL_TOKENS = frozenset(
    {
        "password",
        "passwd",
        "credential",
        "credentials",
        "connection_string",
        "jdbc",
    }
)

_HOSTNAME_VERIFICATION_TOKENS = frozenset(
    {
        "hostname_verification",
        "verify_hostname",
        "hostname_verify",
    }
)

_TLS_VERIFICATION_TOKENS = frozenset(
    {
        "verify_ssl",
        "ssl_verify",
        "tls_verify",
        "verify_tls",
        "trust_all",
        "trustall",
        "insecure",
        "ssl_insecure",
        "tls_insecure",
    }
)

_AUTH_TOKENS = frozenset(
    {
        "authentication",
        "authentication_enabled",
        "auth_enabled",
        "enable_authentication",
        "enable_auth",
    }
)

_CORS_TOKENS = frozenset(
    {
        "allowed_origin",
        "allowed_origins",
        "allowedorigins",
        "cors_allowed_origins",
        "cors_origins",
    }
)

_POLICY_TOKENS = (
    _HOSTNAME_VERIFICATION_TOKENS
    | _TLS_VERIFICATION_TOKENS
    | _AUTH_TOKENS
    | _CORS_TOKENS
    | frozenset({"debug", "ssl", "tls", "cors", "auth", "authorization"})
)

_TOKEN_SPLIT = re.compile(r"[_\-.]+")


def normalize_key(key: str) -> str:
    text = key.strip().replace("-", "_").replace(".", "_").replace("/", "_")
    text = re.sub(r"_+", "_", text)
    return text.lower()


def _tokens(normalized_key: str) -> set[str]:
    parts = [part for part in _TOKEN_SPLIT.split(normalized_key) if part]
    joined = {"_".join(parts[index : index + 2]) for index in range(len(parts) - 1)}
    return set(parts) | joined | {normalized_key}


def is_security_relevant_key(key: str) -> bool:
    tokens = _tokens(normalize_key(key))
    return bool(tokens & (_SENSITIVE_TOKENS | _POLICY_TOKENS))


def is_sensitive_literal_key(key: str) -> bool:
    tokens = _tokens(normalize_key(key))
    return bool(tokens & _SENSITIVE_TOKENS)


def is_flag_or_policy_key(key: str) -> bool:
    tokens = _tokens(normalize_key(key))
    return bool(tokens & _POLICY_TOKENS)


def classify_key_family(key: str) -> ConfigurationKeyFamily:
    """Return typed key family for rule consumption (evidence schema 1.1.0)."""

    normalized = normalize_key(key)
    tokens = _tokens(normalized)

    if tokens & _HOSTNAME_VERIFICATION_TOKENS or (
        "hostname" in tokens and "verification" in tokens
    ):
        return ConfigurationKeyFamily.HOSTNAME_VERIFICATION

    if tokens & _TLS_VERIFICATION_TOKENS or (
        ("ssl" in tokens or "tls" in tokens)
        and ("verify" in tokens or "verification" in tokens or "insecure" in tokens)
    ):
        return ConfigurationKeyFamily.TLS_VERIFICATION

    if tokens & _CORS_TOKENS or (
        "cors" in tokens and ("origin" in tokens or "origins" in tokens)
    ):
        return ConfigurationKeyFamily.CORS_ORIGIN

    if "debug" in tokens:
        return ConfigurationKeyFamily.DEBUG

    if tokens & _AUTH_TOKENS or (
        "auth" in tokens and "enabled" in tokens and "author" not in normalized
    ):
        return ConfigurationKeyFamily.AUTHENTICATION

    if tokens & _SECRET_TOKENS:
        return ConfigurationKeyFamily.SECRET

    if tokens & _CREDENTIAL_TOKENS:
        return ConfigurationKeyFamily.CREDENTIAL

    if is_security_relevant_key(key):
        return ConfigurationKeyFamily.OTHER
    return ConfigurationKeyFamily.UNKNOWN


def value_looks_like_http_endpoint(value: str) -> bool:
    lower = value.strip().lower()
    return lower.startswith("http://")


def parse_literal_boolean(value: str) -> bool | None:
    lower = value.strip().lower()
    if lower in {"true", "yes", "on", "1"}:
        return True
    if lower in {"false", "no", "off", "0"}:
        return False
    return None


def is_explicit_wildcard_origin(value: str) -> bool:
    return value.strip() == "*"
