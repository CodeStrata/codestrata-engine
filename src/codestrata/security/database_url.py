"""Database URL redaction for diagnostics and error messages."""

from __future__ import annotations

from urllib.parse import quote, unquote, urlparse, urlunparse

# Query keys that may carry secrets and must never appear in diagnostics.
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "sslpassword",
    }
)


def redact_database_url(url: str | None) -> str:
    """Return a display-safe database URL with credentials redacted.

    Examples::

        postgresql://user:secret@localhost:5432/db
        → postgresql://user:***@localhost:5432/db

        postgresql://user@localhost:5432/db
        → postgresql://user@localhost:5432/db  (no invented password)
    """

    if url is None:
        return ""
    compact = str(url).strip()
    if not compact:
        return ""

    try:
        parsed = urlparse(compact)
    except Exception:  # noqa: BLE001 - never fail redaction
        return _fallback_redact(compact)

    if not parsed.scheme or not parsed.netloc:
        return _fallback_redact(compact)

    username = unquote(parsed.username) if parsed.username is not None else None
    password = parsed.password  # present (possibly empty) vs absent

    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""

    if username is not None:
        userinfo = quote(username, safe="")
        if password is not None:
            userinfo = f"{userinfo}:***"
        netloc = f"{userinfo}@{host}{port}"
    else:
        netloc = f"{host}{port}"

    query = _redact_query(parsed.query)
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


def _redact_query(query: str) -> str:
    if not query:
        return ""
    parts: list[str] = []
    for item in query.split("&"):
        if not item:
            continue
        if "=" not in item:
            parts.append(item)
            continue
        key, _, value = item.partition("=")
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            parts.append(f"{key}=***")
        else:
            parts.append(f"{key}={value}" if value or item.endswith("=") else key)
    return "&".join(parts)


def _fallback_redact(text: str) -> str:
    """Best-effort redaction when URL parsing fails."""

    # user:password@ → user:***@
    at = text.find("@")
    if at <= 0:
        return text
    head = text[:at]
    scheme_sep = head.find("://")
    if scheme_sep >= 0:
        prefix = head[: scheme_sep + 3]
        userinfo = head[scheme_sep + 3 :]
    else:
        prefix = ""
        userinfo = head
    if ":" in userinfo:
        user, _, _password = userinfo.partition(":")
        return f"{prefix}{user}:***{text[at:]}"
    return text


def sanitize_exception_message(message: str, *, database_url: str | None = None) -> str:
    """Redact secrets from an exception or health message."""

    from codestrata.security.redaction import redact_secrets

    sanitized = redact_secrets(message)
    if database_url:
        compact = database_url.strip()
        if compact and compact in sanitized:
            sanitized = sanitized.replace(compact, redact_database_url(compact))
        # Also redact raw password if parseable.
        try:
            parsed = urlparse(compact)
            if parsed.password:
                raw = unquote(parsed.password)
                if raw and raw in sanitized:
                    sanitized = sanitized.replace(raw, "***")
        except Exception:  # noqa: BLE001
            pass
    return sanitized
