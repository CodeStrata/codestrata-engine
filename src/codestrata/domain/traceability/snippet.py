"""RedactedSnippet — bounded, fail-closed customer-facing excerpt envelope.

IMPORTANT: Callers MUST redact content before constructing this model.
``RedactedSnippet`` records declared redaction state; it does not redact.
It is not safe to store arbitrary raw source code or secrets in ``text``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.traceability.enums import SnippetRedactionLevel, SnippetSourceKind
from codestrata.domain.traceability.validators import (
    MAX_SNIPPET_CHARS,
    TraceabilityValidationError,
    ensure_fail_closed_redaction,
    normalize_limitations,
)


class RedactedSnippet(BaseModel):
    """Customer-safe, bounded excerpt for traceability presentation.

    Construction contract:
    - ``text`` must already be redacted (or proven nonsensitive).
    - ``redaction_level`` must be fail-closed (not ``unredacted`` / ``unknown``).
    - Length is bounded to ``MAX_SNIPPET_CHARS``; longer input is truncated and
      ``truncated`` is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    redaction_level: SnippetRedactionLevel
    fingerprint: str | None = None
    redaction_reasons: tuple[str, ...] = ()
    source_kind: SnippetSourceKind = SnippetSourceKind.SOURCE_EXCERPT
    truncated: bool = False

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="snippet text")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def normalize_fingerprint(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="snippet fingerprint")

    @field_validator("redaction_reasons", mode="before")
    @classmethod
    def normalize_reasons(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        # Reuse limitation-style unique sorted normalization for reasons.
        return normalize_limitations(value)

    @field_validator("redaction_level", mode="before")
    @classmethod
    def coerce_level(cls, value: object) -> object:
        if isinstance(value, SnippetRedactionLevel):
            return value
        if isinstance(value, str):
            return SnippetRedactionLevel(value.strip().lower())
        return value

    @model_validator(mode="before")
    @classmethod
    def bound_text(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        text = payload.get("text")
        if isinstance(text, str) and len(text) > MAX_SNIPPET_CHARS:
            payload["text"] = text[:MAX_SNIPPET_CHARS]
            payload["truncated"] = True
        return payload

    @model_validator(mode="after")
    def validate_redaction(self) -> RedactedSnippet:
        ensure_fail_closed_redaction(self.redaction_level)
        if len(self.text) > MAX_SNIPPET_CHARS:
            raise TraceabilityValidationError(
                f"snippet text exceeds {MAX_SNIPPET_CHARS} characters"
            )
        return self
