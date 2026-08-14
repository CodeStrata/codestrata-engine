"""Community ``codestrata ai`` onboarding / doctor regression tests."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from codestrata.ai.providers.doctor import (
    ConfigStatus,
    build_ai_configuration_report,
)
from codestrata.cli import app
from codestrata.cli.ai_cmd import FRIENDLY_FALLBACK
from codestrata.config.settings import CodestrataSettings

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _visible_help(result) -> str:
    """Normalize CLI help for flag assertions (strip ANSI; collapse whitespace)."""

    raw = f"{result.stdout or ''}{result.stderr or ''}"
    return re.sub(r"\s+", " ", _ANSI_RE.sub("", raw))


def _write_config(path: Path, *, provider: str = "bedrock") -> Path:
    path.write_text(
        "\n".join(
            [
                'profile = "community"',
                "",
                "[repository]",
                'path = "."',
                "",
                "[ai]",
                f'provider = "{provider}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_ai_onboarding_screen() -> None:
    result = runner.invoke(app, ["ai", "--help"])
    assert result.exit_code == 0
    help_text = _visible_help(result)
    assert "doctor" in help_text
    assert "--provider" in help_text

    status = runner.invoke(app, ["ai"])
    assert status.exit_code == 0
    out = status.stdout
    assert "AI is optional" in out
    assert (
        "works fully without AI" in out or "works without AI" in out.lower() or "without AI" in out
    )
    assert "executive summaries" in out.lower() or "recommendations" in out.lower()
    assert "Amazon Bedrock (Recommended)" in out
    assert "OpenAI" in out
    assert "codestrata ai --provider platform" not in out
    assert "codestrata.ai/community/vs-platform" in out or "/community/vs-platform" in out
    assert "Current provider:" in out
    assert "codestrata ai doctor" in out
    assert FRIENDLY_FALLBACK.splitlines()[0] in out
    assert "sk-" not in out
    assert "AKIA" not in out


def test_ai_provider_guides() -> None:
    bedrock = runner.invoke(app, ["ai", "--provider", "bedrock"])
    assert bedrock.exit_code == 0
    assert "aws configure sso" in bedrock.stdout
    assert "AWS_PROFILE" in bedrock.stdout
    assert "aws sts get-caller-identity" in bedrock.stdout
    assert "codestrata ai doctor" in bedrock.stdout
    assert FRIENDLY_FALLBACK.splitlines()[0] in bedrock.stdout

    openai = runner.invoke(app, ["ai", "--provider", "openai"])
    assert openai.exit_code == 0
    assert "OPENAI_API_KEY" in openai.stdout
    assert "OPENAI_BASE_URL" in openai.stdout
    assert "codestrata ai doctor" in openai.stdout
    assert FRIENDLY_FALLBACK.splitlines()[0] in openai.stdout

    platform = runner.invoke(app, ["ai", "--provider", "platform"])
    assert platform.exit_code == 2
    out = platform.stdout + platform.stderr
    assert "not an AI provider" in out

    bad = runner.invoke(app, ["ai", "--provider", "nope"])
    assert bad.exit_code == 2


def test_ai_doctor_reports_missing_openai_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = _write_config(tmp_path / "codestrata.toml", provider="openai")
    result = runner.invoke(app, ["ai", "doctor", "--config", str(config)])
    assert result.exit_code == 1
    out = result.stdout + result.stderr
    assert "OPENAI_API_KEY missing" in out or "OPENAI_API_KEY" in out
    assert "✗" in out
    assert FRIENDLY_FALLBACK.splitlines()[0] in out
    assert "sk-" not in out


def test_ai_doctor_unsupported_provider(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "codestrata.toml", provider="not-a-real-provider")
    result = runner.invoke(app, ["ai", "doctor", "--config", str(config)])
    assert result.exit_code == 1
    out = result.stdout + result.stderr
    assert "Unsupported provider" in out


def test_ai_doctor_reports_credential_source_for_bedrock(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AWS_PROFILE", "doctor-profile")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)

    class _Creds:
        pass

    class _Sts:
        def get_caller_identity(self) -> dict[str, str]:
            return {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/doctor",
                "UserId": "AIDATEST",
            }

    class _Session:
        region_name = "us-east-1"

        def get_credentials(self) -> _Creds:
            return _Creds()

        def client(self, service_name: str, region_name: str | None = None) -> _Sts:
            assert service_name == "sts"
            return _Sts()

    config = _write_config(tmp_path / "codestrata.toml", provider="bedrock")
    from unittest.mock import patch

    with patch("boto3.Session", return_value=_Session()):
        result = runner.invoke(app, ["ai", "doctor", "--config", str(config)])
    out = result.stdout + result.stderr
    assert result.exit_code == 0
    assert "Bedrock configured" in out
    assert "doctor-profile" in out
    assert "sk-" not in out
    assert "AKIA" not in out


def test_assess_help_documents_with_ai() -> None:
    result = runner.invoke(app, ["assess", "--help"])
    assert result.exit_code == 0
    help_text = _visible_help(result)
    assert "--with-ai" in help_text
    assert "codestrata ai" in help_text or "docs.codestrata.ai/ai-providers" in help_text


def test_build_report_marks_openai_when_key_present(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-secret-for-assert")
    settings = CodestrataSettings.model_validate(
        {
            "profile": "community",
            "repository": {"path": "."},
            "ai": {"provider": "openai"},
        }
    )
    report = build_ai_configuration_report(settings)
    openai = next(item for item in report.providers if item.name == "openai")
    assert openai.status is ConfigStatus.CONFIGURED
    serialized = str(report)
    assert "test-key-not-a-secret-for-assert" not in serialized
