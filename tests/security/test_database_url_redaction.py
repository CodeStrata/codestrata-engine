"""Unit tests for database URL redaction."""

from __future__ import annotations

from codestrata.security.database_url import redact_database_url, sanitize_exception_message


def test_redact_password_in_database_url() -> None:
    raw = "postgresql://user:secret@localhost:5432/codestrata"
    assert redact_database_url(raw) == "postgresql://user:***@localhost:5432/codestrata"
    assert "secret" not in redact_database_url(raw)


def test_redact_url_without_password_does_not_invent_one() -> None:
    raw = "postgresql://user@localhost:5432/codestrata"
    assert redact_database_url(raw) == "postgresql://user@localhost:5432/codestrata"
    assert "***" not in redact_database_url(raw)


def test_redact_url_encoded_password() -> None:
    raw = "postgresql://user:p%40ss%3Aword@localhost:5432/codestrata"
    redacted = redact_database_url(raw)
    assert "p%40ss" not in redacted
    assert "p@ss" not in redacted
    assert redacted == "postgresql://user:***@localhost:5432/codestrata"


def test_redact_sensitive_query_params() -> None:
    raw = "postgresql://user:secret@host/db?sslmode=require&password=extra"
    redacted = redact_database_url(raw)
    assert "secret" not in redacted
    assert "password=***" in redacted
    assert "sslmode=require" in redacted


def test_sanitize_exception_message_strips_url_and_password() -> None:
    url = "postgresql://codestrata:hunter2@localhost:5432/codestrata"
    message = f"could not connect to server: {url} password=hunter2"
    sanitized = sanitize_exception_message(message, database_url=url)
    assert "hunter2" not in sanitized
    assert "[REDACTED]" in sanitized or "***" in sanitized
