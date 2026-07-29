"""Tests for shared secret redaction."""

from __future__ import annotations

from codestrata.security.redaction import REDACTED, Redactor, redact_secrets


def test_exact_token_redaction() -> None:
    secret = "exact-secret-value-12345"
    assert REDACTED in Redactor(secrets=[secret]).redact(f"token={secret}")


def test_url_encoded_token_redaction() -> None:
    secret = "a/b+c=d"
    text = f"https://x:{secret}@github.com/org/repo.git"
    sanitized = Redactor(secrets=[secret]).redact(text)
    assert secret not in sanitized
    assert REDACTED in sanitized


def test_sqlalchemy_dialect_connection_string_redaction() -> None:
    text = "failed: postgresql+psycopg://codestrata:SuperSecretPass@127.0.0.1:5432/codestrata"
    sanitized = redact_secrets(text)
    assert "SuperSecretPass" not in sanitized
    assert REDACTED in sanitized
    assert "postgresql+psycopg://" in sanitized


def test_mysql_dialect_connection_string_redaction() -> None:
    text = "mysql+pymysql://root:hunter2@db.internal/app"
    sanitized = redact_secrets(text)
    assert "hunter2" not in sanitized
    assert REDACTED in sanitized


def test_authorization_bearer_and_basic() -> None:
    bearer = "Authorization: Bearer abcdef123456"
    basic = "Authorization: Basic dXNlcjpwYXNz"
    assert "abcdef123456" not in redact_secrets(bearer)
    assert "dXNlcjpwYXNz" not in redact_secrets(basic)


def test_openai_style_and_bearer_assignment_redaction() -> None:
    key = "sk-" + ("x" * 20)
    assert key not in redact_secrets(f"provider failed key={key}")
    assert "tokensecret" not in redact_secrets("boom bearer=tokensecret")


def test_github_style_token_patterns() -> None:
    classic = "ghp_" + ("a" * 36)
    fine = "github_pat_" + ("b" * 40)
    assert classic not in redact_secrets(f"token {classic}")
    assert fine not in redact_secrets(f"token {fine}")


def test_repeated_and_embedded_secrets() -> None:
    secret = "repeat-me-please"
    text = f"{secret} failed with {secret} in stderr"
    sanitized = Redactor(secrets=[secret]).redact(text)
    assert secret not in sanitized
    assert sanitized.count(REDACTED) >= 2


def test_helper_path_redaction() -> None:
    path = "/tmp/codestrata-git-auth-xyz/codestrata-askpass.sh"
    sanitized = Redactor(helper_paths=[path]).redact(f"helper={path}")
    assert path not in sanitized
    assert REDACTED in sanitized


def test_already_redacted_remains_stable() -> None:
    text = f"value={REDACTED}"
    assert redact_secrets(text) == text


def test_none_and_empty() -> None:
    assert redact_secrets(None) == ""
    assert redact_secrets("") == ""


def test_unicode_around_secret() -> None:
    secret = "secret-ユニコード"
    text = f"前{secret}後"
    sanitized = Redactor(secrets=[secret]).redact(text)
    assert secret not in sanitized
    assert "前" in sanitized and "後" in sanitized
