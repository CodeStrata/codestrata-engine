"""Tests for RedactedSnippet."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.traceability import (
    MAX_SNIPPET_CHARS,
    RedactedSnippet,
    SnippetRedactionLevel,
    to_stable_dict,
)


def test_valid_redacted_snippet() -> None:
    snippet = RedactedSnippet(
        text="password=***",
        redaction_level=SnippetRedactionLevel.PARTIALLY_REDACTED,
        redaction_reasons=("credential_pattern",),
        fingerprint="abc123",
    )
    assert snippet.fingerprint == "abc123"
    assert snippet.redaction_reasons == ("credential_pattern",)


def test_rejects_unredacted_level() -> None:
    with pytest.raises(ValidationError, match="fail-closed"):
        RedactedSnippet(
            text="secret-token-value",
            redaction_level=SnippetRedactionLevel.UNREDACTED,
        )


def test_rejects_unknown_level() -> None:
    with pytest.raises(ValidationError, match="fail-closed"):
        RedactedSnippet(
            text="maybe sensitive",
            redaction_level=SnippetRedactionLevel.UNKNOWN,
        )


def test_truncates_overlong_text() -> None:
    text = "x" * (MAX_SNIPPET_CHARS + 50)
    snippet = RedactedSnippet(
        text=text,
        redaction_level=SnippetRedactionLevel.SAFE_NONSENSITIVE,
    )
    assert len(snippet.text) == MAX_SNIPPET_CHARS
    assert snippet.truncated is True


def test_deterministic_serialization() -> None:
    snippet = RedactedSnippet(
        text="ok",
        redaction_level=SnippetRedactionLevel.SAFE_NONSENSITIVE,
        redaction_reasons=("b", "a"),
    )
    first = to_stable_dict(snippet)
    second = to_stable_dict(snippet)
    assert first == second
    assert list(first.keys()) == sorted(first.keys())
    assert first["redaction_reasons"] == ["a", "b"]
