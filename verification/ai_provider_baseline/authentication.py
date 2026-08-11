"""Characterize credential/authentication boundaries with mocked clients only.

Never performs a real AWS or OpenAI network call. AWS session construction is
patched at ``codestrata.ai.aws_config.build_boto3_session``; OpenAI credential
checks only ever read an environment variable *name*, and any injected value
used here is an obvious placeholder, never a real secret.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from codestrata.ai import aws_config
from codestrata.config.settings import CodestrataSettings, RepositorySettings
from verification.ai_provider_baseline.models import CheckResult

_PLACEHOLDER_OPENAI_KEY = "sk-baseline-placeholder-not-a-real-key"  # noqa: S105
_AWS_ENV_KEYS = ("AWS_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION")


@contextmanager
def _hermetic_aws_env() -> Iterator[None]:
    """Temporarily remove host AWS_* env vars so probes are host-independent."""

    saved = {key: os.environ.pop(key, None) for key in _AWS_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def _settings() -> CodestrataSettings:
    return CodestrataSettings(repository=RepositorySettings(path="."))


def _fake_session(
    *, credentials: object | None, identity_error: Exception | None = None
) -> MagicMock:
    session = MagicMock(name="fake_boto3_session")
    session.region_name = "us-east-1"
    session.get_credentials.return_value = credentials
    sts_client = MagicMock(name="fake_sts_client")
    if identity_error is not None:
        sts_client.get_caller_identity.side_effect = identity_error
    else:
        sts_client.get_caller_identity.return_value = {"Account": "000000000000"}
    session.client.return_value = sts_client
    return session


def probe_scenarios() -> list[dict[str, object]]:
    """Run ``probe_aws_session_for_bedrock`` across mocked credential states."""

    settings = _settings()
    results: list[dict[str, object]] = []

    with _hermetic_aws_env():
        with patch.object(
            aws_config,
            "build_boto3_session",
            return_value=_fake_session(
                credentials=SimpleNamespace(access_key="AKIAFAKEPLACEHOLDER")
            ),
        ):
            probe_ok = aws_config.probe_aws_session_for_bedrock(
                settings=settings, profile=None, region="us-east-1"
            )
        results.append(
            {
                "expected_ok": True,
                "ok": probe_ok.ok,
                "scenario": "credentials_present_region_set",
            }
        )

        with patch.object(
            aws_config,
            "build_boto3_session",
            return_value=_fake_session(credentials=None),
        ):
            probe_missing = aws_config.probe_aws_session_for_bedrock(
                settings=settings, profile=None, region="us-east-1"
            )
        results.append(
            {
                "expected_ok": False,
                "ok": probe_missing.ok,
                "scenario": "credentials_missing",
            }
        )

        fake_region_session = _fake_session(
            credentials=SimpleNamespace(access_key="AKIAFAKEPLACEHOLDER")
        )
        fake_region_session.region_name = None
        with patch.object(aws_config, "build_boto3_session", return_value=fake_region_session):
            probe_no_region = aws_config.probe_aws_session_for_bedrock(
                settings=settings, profile=None, region=None
            )
        results.append(
            {
                "expected_ok": False,
                "ok": probe_no_region.ok,
                "scenario": "region_missing",
            }
        )

        with patch.object(
            aws_config,
            "build_boto3_session",
            return_value=_fake_session(
                credentials=SimpleNamespace(access_key="AKIAFAKEPLACEHOLDER"),
                identity_error=RuntimeError("ExpiredTokenException (mocked)"),
            ),
        ):
            probe_expired = aws_config.probe_aws_session_for_bedrock(
                settings=settings, profile=None, region="us-east-1"
            )
        results.append(
            {
                "expected_ok": False,
                "ok": probe_expired.ok,
                "scenario": "authentication_failure",
            }
        )

    results.sort(key=lambda item: str(item["scenario"]))
    return results


def check_probe_scenarios_match_expected(_source_root: Path) -> CheckResult:
    scenarios = probe_scenarios()
    mismatches = [s for s in scenarios if s["ok"] != s["expected_ok"]]
    return CheckResult(
        name="aws_probe_scenarios_match_expected_outcomes",
        category="authentication",
        ok=not mismatches,
        detail=f"scenarios={len(scenarios)} mismatches={len(mismatches)}",
        evidence={"scenarios": scenarios},
    )


def check_no_real_boto3_session_constructed(_source_root: Path) -> CheckResult:
    """Confirm the mocked boundary is actually exercised (not silently bypassed)."""

    settings = _settings()
    fake_session = _fake_session(credentials=SimpleNamespace(access_key="AKIAFAKEPLACEHOLDER"))
    with (
        _hermetic_aws_env(),
        patch.object(aws_config, "build_boto3_session", return_value=fake_session) as mocked,
    ):
        aws_config.probe_aws_session_for_bedrock(
            settings=settings, profile=None, region="us-east-1"
        )
        called = mocked.called
    return CheckResult(
        name="aws_session_construction_boundary_is_mockable",
        category="authentication",
        ok=called,
        detail=f"build_boto3_session called={called} (patched boundary observed)",
    )


def openai_key_presence_scenarios() -> list[dict[str, object]]:
    env_name = "CODESTRATA_BASELINE_FAKE_OPENAI_KEY"
    scenarios: list[dict[str, object]] = []

    original = os.environ.pop(env_name, None)
    try:
        scenarios.append(
            {
                "expected_present": False,
                "present": bool(os.environ.get(env_name, "").strip()),
                "scenario": "env_var_unset",
            }
        )
        os.environ[env_name] = _PLACEHOLDER_OPENAI_KEY
        scenarios.append(
            {
                "expected_present": True,
                "present": bool(os.environ.get(env_name, "").strip()),
                "scenario": "env_var_set_to_placeholder",
            }
        )
    finally:
        if original is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = original

    scenarios.sort(key=lambda item: str(item["scenario"]))
    return scenarios


def check_openai_key_presence_scenarios(_source_root: Path) -> CheckResult:
    scenarios = openai_key_presence_scenarios()
    mismatches = [s for s in scenarios if s["present"] != s["expected_present"]]
    return CheckResult(
        name="openai_api_key_env_presence_scenarios_match_expected",
        category="authentication",
        ok=not mismatches,
        detail=f"scenarios={len(scenarios)} mismatches={len(mismatches)}",
        evidence={
            "scenarios": [
                {
                    "expected_present": s["expected_present"],
                    "present": s["present"],
                    "scenario": s["scenario"],
                }
                for s in scenarios
            ]
        },
    )


def run_authentication_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_probe_scenarios_match_expected(source_root),
        check_no_real_boto3_session_constructed(source_root),
        check_openai_key_presence_scenarios(source_root),
    ]
    matrix = {
        "aws_probe_scenarios": probe_scenarios(),
        "openai_key_presence_scenarios": openai_key_presence_scenarios(),
    }
    return checks, matrix


__all__ = [
    "check_no_real_boto3_session_constructed",
    "check_openai_key_presence_scenarios",
    "check_probe_scenarios_match_expected",
    "openai_key_presence_scenarios",
    "probe_scenarios",
    "run_authentication_checks",
]
