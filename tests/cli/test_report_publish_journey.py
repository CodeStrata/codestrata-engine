"""Unit tests for Community report publish journey (Slice 18.7 fix)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.cli.report import report_app
from codestrata.community_cloud.report_publishing import (
    PUBLIC_PUBLISH_WARNING,
    resolve_community_credential,
    telemetry_eligible_for_publish,
    user_facing_publish_error,
    ReportPublishError,
)
from codestrata.telemetry.consent import deny_session_consent
from codestrata.telemetry.session import TelemetrySession


runner = CliRunner()


def test_resolve_credential_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL", raising=False)
    monkeypatch.delenv("CODESTRATA_TELEMETRY_OPT_IN", raising=False)
    cred = resolve_community_credential()
    assert cred.authorization_header_value().startswith("Bearer cscc_v1_")


def test_publish_eligibility_independent_of_telemetry() -> None:
    assert telemetry_eligible_for_publish(None) is True
    assert (
        telemetry_eligible_for_publish(TelemetrySession(consent=deny_session_consent()))
        is True
    )


def test_user_facing_errors_hide_operator_guidance() -> None:
    msg = user_facing_publish_error(
        ReportPublishError("Missing CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL / AWS secret")
    )
    assert "CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL" not in msg
    assert "AWS" not in msg
    assert "Local report remains unchanged" in msg


def test_noninteractive_requires_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CI", "1")
    monkeypatch.delenv("CODESTRATA_FORCE_INTERACTIVE", raising=False)
    monkeypatch.delenv("CODESTRATA_TELEMETRY_OPT_IN", raising=False)
    monkeypatch.delenv("CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL", raising=False)
    root = tmp_path / ".codestrata-artifacts" / "assessments" / "local-demo" / "current"
    root.mkdir(parents=True)
    (root / "assessment.html").write_text("<html></html>", encoding="utf-8")
    (root / "assessment.json").write_text("{}", encoding="utf-8")
    result = runner.invoke(
        report_app,
        ["publish", "--artifacts-root", str(tmp_path / ".codestrata-artifacts")],
    )
    assert result.exit_code == 2
    assert "--confirm-public-publish" in (result.stdout + result.stderr)


def test_noninteractive_private_requires_ack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CI", "1")
    monkeypatch.delenv("CODESTRATA_FORCE_INTERACTIVE", raising=False)
    root = tmp_path / ".codestrata-artifacts" / "assessments" / "local-demo" / "current"
    root.mkdir(parents=True)
    (root / "assessment.html").write_text("<html></html>", encoding="utf-8")
    (root / "assessment.json").write_text("{}", encoding="utf-8")
    result = runner.invoke(
        report_app,
        [
            "publish",
            "--artifacts-root",
            str(tmp_path / ".codestrata-artifacts"),
            "--confirm-public-publish",
        ],
    )
    assert result.exit_code == 2
    assert "acknowledge-private-repository" in (result.stdout + result.stderr).lower() or (
        "private/local" in (result.stdout + result.stderr).lower()
    )


def test_help_recommends_interactive_path() -> None:
    result = runner.invoke(report_app, ["publish", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "codestrata report publish" in out
    assert "CODESTRATA_TELEMETRY_OPT_IN" not in out
    assert "CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL" not in out
    assert PUBLIC_PUBLISH_WARNING.split(".")[0] in out or "Interactive" in out or "confirm" in out.lower()


def test_verify_public_report_get_rejects_api_json_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.community_cloud import report_publishing as rp

    class _FakeResp:
        status = 404
        headers = {"Content-Type": "application/json"}

        def read(self, _n: int = -1) -> bytes:
            return (
                b'{"error":{"code":"not_found","message":"Endpoint not found."}}'
            )

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    class _FakeOpener:
        def open(self, request: object, timeout: float = 0) -> _FakeResp:  # noqa: ARG002
            raise rp.urllib.error.HTTPError(
                url="https://reports.codestrata.ai/r/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                code=404,
                msg="Not Found",
                hdrs=None,  # type: ignore[arg-type]
                fp=None,
            )

    monkeypatch.setattr(
        rp.urllib.request,
        "build_opener",
        lambda *args, **kwargs: _FakeOpener(),  # noqa: ARG005
    )
    with pytest.raises(ReportPublishError, match="did not return a readable"):
        rp.verify_public_report_get(
            "https://reports.codestrata.ai/r/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            expected_public_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )


def test_verify_public_report_get_rejects_url_constructor_mismatch() -> None:
    from codestrata.community_cloud.report_publishing import verify_public_report_get

    with pytest.raises(ReportPublishError, match="branded"):
        verify_public_report_get(
            "https://api.codestrata.ai/api/v1/reports/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            expected_public_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )


def test_cli_and_policy_public_url_prefix_align() -> None:
    from codestrata.community_cloud.report_publishing import PUBLIC_REPORTS_BASE_URL

    assert PUBLIC_REPORTS_BASE_URL == "https://reports.codestrata.ai"
    assert f"{PUBLIC_REPORTS_BASE_URL}/r/" == "https://reports.codestrata.ai/r/"
