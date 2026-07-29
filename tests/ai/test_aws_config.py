"""Tests for centralized AWS configuration and Bedrock client creation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codestrata.ai.aws_config import (
    AWS_DEFAULT_REGION_ENV,
    AWS_PROFILE_ENV,
    AWS_REGION_ENV,
    AwsAuthenticationError,
    create_bedrock_runtime_client,
    format_aws_authentication_error,
    resolve_aws_config,
)
from codestrata.config import load_settings


def _settings(tmp_path: Path, body: str):
    config = tmp_path / "codestrata.toml"
    config.write_text(body, encoding="utf-8")
    return load_settings(config)


def test_resolve_aws_config_from_codestrata_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(AWS_PROFILE_ENV, raising=False)
    monkeypatch.delenv(AWS_REGION_ENV, raising=False)
    monkeypatch.delenv(AWS_DEFAULT_REGION_ENV, raising=False)
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [aws]
        profile = "codestrata"
        region = "us-east-1"
        """,
    )
    resolved = resolve_aws_config(settings=settings)
    assert resolved.profile == "codestrata"
    assert resolved.region == "us-east-1"
    assert "codestrata.toml" in resolved.source_profile
    assert "codestrata.toml" in resolved.source_region


def test_resolve_aws_config_from_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(AWS_PROFILE_ENV, "env-profile")
    monkeypatch.setenv(AWS_REGION_ENV, "eu-west-1")
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"
        """,
    )
    resolved = resolve_aws_config(settings=settings)
    assert resolved.profile == "env-profile"
    assert resolved.region == "eu-west-1"
    assert AWS_PROFILE_ENV in resolved.source_profile
    assert AWS_REGION_ENV in resolved.source_region


def test_environment_overrides_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 5.20: environment variables override codestrata.toml AWS settings."""

    monkeypatch.setenv(AWS_PROFILE_ENV, "env-profile")
    monkeypatch.setenv(AWS_REGION_ENV, "eu-west-1")
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [aws]
        profile = "codestrata"
        region = "us-east-1"
        """,
    )
    resolved = resolve_aws_config(settings=settings)
    assert resolved.profile == "env-profile"
    assert resolved.region == "eu-west-1"
    assert AWS_PROFILE_ENV in resolved.source_profile
    assert AWS_REGION_ENV in resolved.source_region


def test_legacy_bedrock_region_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AWS_REGION_ENV, raising=False)
    monkeypatch.delenv(AWS_DEFAULT_REGION_ENV, raising=False)
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [ai.bedrock]
        region = "ap-southeast-2"
        """,
    )
    resolved = resolve_aws_config(settings=settings)
    assert resolved.region == "ap-southeast-2"
    assert "ai.bedrock" in resolved.source_region


def test_default_boto3_session_when_unconfigured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AWS_PROFILE_ENV, raising=False)
    monkeypatch.delenv(AWS_REGION_ENV, raising=False)
    monkeypatch.delenv(AWS_DEFAULT_REGION_ENV, raising=False)
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"
        """,
    )
    resolved = resolve_aws_config(settings=settings)
    assert resolved.profile is None
    assert resolved.region is None
    assert "default credential chain" in resolved.source_profile
    assert "default region chain" in resolved.source_region


def test_missing_region_still_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(AWS_REGION_ENV, raising=False)
    monkeypatch.delenv(AWS_DEFAULT_REGION_ENV, raising=False)
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [aws]
        profile = "codestrata"
        """,
    )
    resolved = resolve_aws_config(settings=settings)
    assert resolved.profile == "codestrata"
    assert resolved.region is None


def test_create_bedrock_runtime_client_uses_profile_and_region(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AWS_PROFILE_ENV, raising=False)
    monkeypatch.delenv(AWS_REGION_ENV, raising=False)
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [aws]
        profile = "codestrata"
        region = "us-east-1"
        """,
    )
    session = MagicMock()
    client = MagicMock()
    session.client.return_value = client

    with (
        patch("boto3.Session", return_value=session) as session_factory,
        patch("botocore.config.Config"),
    ):
        result = create_bedrock_runtime_client(
            settings=settings,
            model_id="amazon.nova-lite-v1:0",
        )

    assert result is client
    session_factory.assert_called_once_with(profile_name="codestrata", region_name="us-east-1")
    session.client.assert_called_once()
    assert session.client.call_args.args[0] == "bedrock-runtime"
    assert session.client.call_args.kwargs["region_name"] == "us-east-1"


def test_create_bedrock_runtime_client_default_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AWS_PROFILE_ENV, raising=False)
    monkeypatch.delenv(AWS_REGION_ENV, raising=False)
    monkeypatch.delenv(AWS_DEFAULT_REGION_ENV, raising=False)
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"
        """,
    )
    session = MagicMock()
    session.client.return_value = MagicMock()

    with (
        patch("boto3.Session", return_value=session) as session_factory,
        patch("botocore.config.Config"),
    ):
        create_bedrock_runtime_client(settings=settings)

    session_factory.assert_called_once_with()
    assert "region_name" not in session.client.call_args.kwargs


def test_invalid_profile_raises_friendly_error() -> None:
    from botocore.exceptions import ProfileNotFound

    with (
        patch("boto3.Session", side_effect=ProfileNotFound(profile="missing")),
        patch("botocore.config.Config"),
        pytest.raises(AwsAuthenticationError, match="Unable to authenticate with AWS"),
    ):
        create_bedrock_runtime_client(profile="missing", region="us-east-1")


def test_authentication_error_message_includes_guidance() -> None:
    message = format_aws_authentication_error(profile="my-profile")
    assert "Unable to authenticate with AWS." in message
    assert "aws sso login --profile my-profile" in message
    assert "standard AWS credential provider chain" in message
    assert "AWS_PROFILE" in message
    assert "aws configure" in message
    assert "developer-specific" in message


def test_probe_aws_session_reports_env_profile_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AWS_PROFILE_ENV, "env-profile")
    monkeypatch.setenv(AWS_REGION_ENV, "us-west-2")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)

    class _Creds:
        pass

    class _Sts:
        def get_caller_identity(self) -> dict[str, str]:
            return {"Account": "123", "Arn": "arn:aws:iam::123:user/test", "UserId": "AIDATEST"}

    class _Session:
        region_name = "us-west-2"

        def get_credentials(self) -> _Creds:
            return _Creds()

        def client(self, service_name: str, region_name: str | None = None) -> _Sts:
            assert service_name == "sts"
            return _Sts()

    with patch("boto3.Session", return_value=_Session()):
        from codestrata.ai.aws_config import probe_aws_session_for_bedrock

        probe = probe_aws_session_for_bedrock()
    assert probe.ok is True
    assert probe.resolved.profile == "env-profile"
    assert AWS_PROFILE_ENV in probe.resolved.source_profile
    assert "env-profile" in probe.credential_source
    assert probe.effective_region == "us-west-2"


def test_probe_aws_session_default_chain_without_toml_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AWS_PROFILE_ENV, raising=False)
    monkeypatch.setenv(AWS_REGION_ENV, "eu-west-1")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)

    class _Creds:
        pass

    class _Sts:
        def get_caller_identity(self) -> dict[str, str]:
            return {"Account": "123", "Arn": "arn:aws:iam::123:user/test", "UserId": "AIDATEST"}

    class _Session:
        region_name = "eu-west-1"

        def get_credentials(self) -> _Creds:
            return _Creds()

        def client(self, service_name: str, region_name: str | None = None) -> _Sts:
            assert service_name == "sts"
            return _Sts()

    with patch("boto3.Session", return_value=_Session()) as session_ctor:
        from codestrata.ai.aws_config import probe_aws_session_for_bedrock

        probe = probe_aws_session_for_bedrock()
    assert probe.ok is True
    assert probe.resolved.profile is None
    assert "default credential chain" in probe.credential_source
    # Session built without profile_name (default chain)
    kwargs = session_ctor.call_args.kwargs
    assert "profile_name" not in kwargs
    assert kwargs.get("region_name") == "eu-west-1"


def test_probe_aws_session_rejects_expired_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(AWS_PROFILE_ENV, "expired-profile")
    monkeypatch.setenv(AWS_REGION_ENV, "us-east-1")

    class _Creds:
        pass

    class _Sts:
        def get_caller_identity(self) -> dict[str, str]:
            raise RuntimeError("Token has expired and refresh failed")

    class _Session:
        region_name = "us-east-1"

        def get_credentials(self) -> _Creds:
            return _Creds()

        def client(self, service_name: str, region_name: str | None = None) -> _Sts:
            return _Sts()

    with patch("boto3.Session", return_value=_Session()):
        from codestrata.ai.aws_config import probe_aws_session_for_bedrock

        probe = probe_aws_session_for_bedrock()
    assert probe.ok is False
    assert "Unable to authenticate" in probe.detail
    assert probe.guidance is not None
    assert "aws sso login" in probe.guidance


def test_load_settings_reads_aws_section(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        """
        [repository]
        url = "https://github.com/example/sample-app.git"

        [aws]
        profile = "codestrata"
        region = "us-east-1"

        [ai.bedrock]
        model_id = "amazon.nova-lite-v1:0"
        """,
    )
    assert settings.aws.profile == "codestrata"
    assert settings.aws.region == "us-east-1"
    assert settings.ai.bedrock.model_id == "amazon.nova-lite-v1:0"
