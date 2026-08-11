"""Centralized secret redaction for operational output and report serialization."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from typing import Any
from urllib.parse import quote, unquote

REDACTED = "[REDACTED]"

# Supplementary pattern-based redaction for recognizable credential shapes.
_GITHUB_TOKEN_PATTERN = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})",
)
_BEARER_PATTERN = re.compile(
    r"(?i)(Authorization:\s*Bearer\s+)\S+",
)
_BEARER_ASSIGN_PATTERN = re.compile(
    r"(?i)(bearer\s*[=:]\s*)\S+",
)
_BASIC_PATTERN = re.compile(
    r"(?i)(Authorization:\s*Basic\s+)\S+",
)
_OPENAI_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_URL_USERINFO_PATTERN = re.compile(
    r"(https?://)([^/\s:@]+):([^/\s@]+)@",
)
_HELPER_PATH_PATTERN = re.compile(
    r"(?i)(/[^\s]*codestrata[-_](?:askpass|git-auth)[^\s]*)",
)
_AWS_ACCESS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_AWS_SECRET_ASSIGN_PATTERN = re.compile(
    r"(?i)(aws_secret_access_key\s*[=:]\s*)(\S+)",
)
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----[\s\S]*?"
    r"-----END (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
)
# Header-only markers (no END block) must not reach customer-facing fields.
# Engine SEC002 historically embedded these as evidence/description text.
_PRIVATE_KEY_HEADER_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
    re.IGNORECASE,
)
# Any remaining dashed PEM begin fence (certificate, etc.) is still secret-shaped.
_PEM_BEGIN_FENCE_PATTERN = re.compile(r"-----BEGIN[^\n-]{0,80}-----", re.IGNORECASE)
# Include SQLAlchemy dialect URLs (e.g. postgresql+psycopg://user:pass@host/db).
_CONNECTION_STRING_PATTERN = re.compile(
    r"(?i)\b((?:postgres(?:ql)?(?:\+[A-Za-z0-9_]+)?|mysql(?:\+[A-Za-z0-9_]+)?|"
    r"mongodb(?:\+srv)?|redis|amqp|mssql|sqlserver)://)([^/\s:@]+):([^/\s@]+)@",
)
_ASSIGNMENT_SECRET_PATTERN = re.compile(
    r"(?i)\b("
    r"password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|auth[_-]?token|connection[_-]?string"
    r")\b(\s*[=:]\s*)(?:'(?P<sq>[^']+)'|\"(?P<dq>[^\"]+)\"|(?P<bare>[^\s'\"#,;]+))"
)
_ENV_EXPORT_PATTERN = re.compile(
    r"(?i)\b(export\s+)("
    r"(?:[A-Z0-9_]*_)?(?:PASSWORD|SECRET|TOKEN|API_KEY|ACCESS_KEY|"
    r"PRIVATE_KEY|CLIENT_SECRET|DATABASE_URL|CONNECTION_STRING)"
    r")(\s*=\s*)(?:'(?P<esq>[^']+)'|\"(?P<edq>[^\"]+)\"|(?P<ebare>[^\s'\"#]+))"
)

# Keys whose string values are redacted when walking report JSON trees.
_SENSITIVE_VALUE_KEYS = frozenset(
    {
        "excerpt",
        "snippet",
        "description",
        "title",
        "summary",
        "detail",
        "message",
        "preview",
        "redacted_preview",
        "detected_value",
    }
)


class Redactor:
    """Sanitize secrets from operational text while preserving structure."""

    def __init__(
        self,
        *,
        secrets: Iterable[str] | None = None,
        helper_paths: Iterable[str] | None = None,
    ) -> None:
        self._secrets = [secret for secret in (secrets or []) if secret]
        self._helper_paths = [path for path in (helper_paths or []) if path]

    def with_secrets(self, *secrets: str) -> Redactor:
        """Return a new redactor that also redacts the given secret values."""

        return Redactor(
            secrets=[*self._secrets, *secrets],
            helper_paths=self._helper_paths,
        )

    def with_helper_paths(self, *paths: str) -> Redactor:
        """Return a new redactor that also redacts helper filesystem paths."""

        return Redactor(
            secrets=self._secrets,
            helper_paths=[*self._helper_paths, *paths],
        )

    def redact(self, text: str | None) -> str:
        """Return sanitized text. Exact secret values are always removed."""

        if text is None:
            return ""
        if text == "":
            return ""

        sanitized = text

        for secret in sorted(self._secrets, key=len, reverse=True):
            sanitized = sanitized.replace(secret, REDACTED)
            encoded = quote(secret, safe="")
            if encoded and encoded != secret:
                sanitized = sanitized.replace(encoded, REDACTED)
            try:
                decoded = unquote(secret)
            except Exception:  # noqa: BLE001 - defensive decoding only
                decoded = secret
            if decoded and decoded != secret:
                sanitized = sanitized.replace(decoded, REDACTED)

        for path in sorted(self._helper_paths, key=len, reverse=True):
            sanitized = sanitized.replace(path, REDACTED)

        sanitized = _PRIVATE_KEY_PATTERN.sub(REDACTED, sanitized)
        sanitized = _PRIVATE_KEY_HEADER_PATTERN.sub(REDACTED, sanitized)
        sanitized = _PEM_BEGIN_FENCE_PATTERN.sub(REDACTED, sanitized)
        sanitized = _URL_USERINFO_PATTERN.sub(rf"\1{REDACTED}:{REDACTED}@", sanitized)
        sanitized = _CONNECTION_STRING_PATTERN.sub(
            rf"\1{REDACTED}:{REDACTED}@",
            sanitized,
        )
        sanitized = _BEARER_PATTERN.sub(rf"\1{REDACTED}", sanitized)
        sanitized = _BEARER_ASSIGN_PATTERN.sub(rf"\1{REDACTED}", sanitized)
        sanitized = _BASIC_PATTERN.sub(rf"\1{REDACTED}", sanitized)
        sanitized = _OPENAI_KEY_PATTERN.sub(REDACTED, sanitized)
        sanitized = _GITHUB_TOKEN_PATTERN.sub(REDACTED, sanitized)
        sanitized = _AWS_ACCESS_KEY_PATTERN.sub(REDACTED, sanitized)
        sanitized = _AWS_SECRET_ASSIGN_PATTERN.sub(rf"\1{REDACTED}", sanitized)
        sanitized = _ENV_EXPORT_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}{REDACTED}",
            sanitized,
        )
        sanitized = _ASSIGNMENT_SECRET_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
            sanitized,
        )
        sanitized = _HELPER_PATH_PATTERN.sub(REDACTED, sanitized)

        # Keep already-redacted markers stable under repeated application.
        sanitized = sanitized.replace(f"{REDACTED}{REDACTED}", REDACTED)
        return sanitized


def redact_secrets(
    text: str | None,
    *,
    secrets: Iterable[str] | None = None,
    helper_paths: Iterable[str] | None = None,
) -> str:
    """Convenience wrapper around :class:`Redactor`."""

    return Redactor(secrets=secrets, helper_paths=helper_paths).redact(text)


def redact_report_value(value: Any, *, key: str | None = None) -> Any:
    """Redact string leaf values that may carry source snippets or secrets.

    Paths and identifiers are preserved. Nested mappings/lists are walked.
    """

    if isinstance(value, Mapping):
        return {
            str(child_key): redact_report_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_report_value(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [redact_report_value(item, key=key) for item in value]
    if isinstance(value, str):
        if key in {"path", "relative_path", "file", "id", "rule_id", "source_id", "node_id"}:
            return value
        if key is None or key in _SENSITIVE_VALUE_KEYS or key.endswith("_excerpt"):
            return redact_secrets(value)
        # Still apply pattern redaction to other strings (defensive).
        return redact_secrets(value)
    return value


def redact_report_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied payload with likely secrets masked for serialization."""

    redacted = redact_report_value(dict(payload))
    if not isinstance(redacted, MutableMapping):
        return dict(payload)
    return dict(redacted)


def redact_finding_dicts(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Redact finding title/description/evidence excerpts; keep paths."""

    return [dict(redact_report_value(dict(item))) for item in findings]
