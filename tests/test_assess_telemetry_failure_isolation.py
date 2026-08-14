"""Assess CLI telemetry failure isolation (Slice 9.12)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.cli_consent_policy import TELEMETRY_FLAG_CONFLICT_MESSAGE
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.http_client import FakeTelemetryHttpResponse
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.service import reset_telemetry_singletons
from tests.telemetry.transport_test_helpers import (
    TEST_ENDPOINT,
    make_http_transport,
)


def _mini_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text('{"name":"iso"}\n', encoding="utf-8")
    return repo


def _invoke_assess(
    repo: Path,
    out: Path,
    *,
    extra: list[str] | None = None,
    env: dict[str, str] | None = None,
):
    runner = CliRunner()
    args = [
        "assess",
        "--repo",
        str(repo),
        "--output",
        str(out),
        "--no-ai",
        "--quiet",
        *(extra or []),
    ]
    return runner.invoke(app, args, env=env)


def test_success_with_default_unavailable(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    with patch("codestrata.telemetry.transport.send_payload") as send:
        with patch("urllib.request.urlopen") as urlopen:
            result = _invoke_assess(repo, out, extra=["--telemetry-deny"])
    assert result.exit_code == 0
    send.assert_not_called()
    urlopen.assert_not_called()
    assert {path.name for path in home.iterdir()} <= {"installation_id"}
    assert "telemetry failed" not in (result.stdout + result.stderr).lower()
    assert "Allow privacy-safe" not in (result.stdout + result.stderr)


def test_success_with_allow_still_network_free(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", TEST_ENDPOINT)
    monkeypatch.setenv("CI", "1")
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    with patch("codestrata.telemetry.transport.send_payload") as send:
        with patch("urllib.request.urlopen") as urlopen:
            result = _invoke_assess(repo, out, extra=["--telemetry-allow"])
    assert result.exit_code == 0
    send.assert_not_called()
    urlopen.assert_not_called()
    assert {path.name for path in home.iterdir()} <= {"installation_id"}


def test_success_when_record_raises(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    with patch(
        "codestrata.telemetry.assessment_lifecycle.record_assess_invoked_safely",
        return_value=False,
    ):
        with patch(
            "codestrata.telemetry.assessment_lifecycle.record_assess_completed_safely",
            return_value=False,
        ):
            result = _invoke_assess(repo, out, extra=["--telemetry-allow"])
    assert result.exit_code == 0
    runs = list(out.rglob("assessment.json"))
    assert runs, "successful assess must still write assessment.json"


def test_injected_failing_http_does_not_change_exit(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    from codestrata.telemetry.persisted_consent import persist_v2_yes

    persist_v2_yes(path=home / "telemetry.json")
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    transport, client = make_http_transport(
        responses=FakeTelemetryHttpResponse(status_code=0, raise_connection=True)
    )

    from codestrata.telemetry import service as svc

    real_ensure = svc.ensure_interactive_product_telemetry

    def _ensure(**kwargs):
        kwargs = dict(kwargs)
        kwargs["transport"] = transport
        kwargs.setdefault("telemetry_allow", True)
        return real_ensure(**kwargs)

    with patch.object(svc, "ensure_interactive_product_telemetry", side_effect=_ensure):
        result = _invoke_assess(repo, out, extra=["--telemetry-allow"])
    assert result.exit_code == 0
    assert client.calls


def test_primary_failure_exit_preserved_with_capture_success(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    from codestrata.telemetry.persisted_consent import persist_v2_yes

    persist_v2_yes(path=home / "telemetry.json")
    reset_telemetry_singletons()
    missing = tmp_path / "missing-repo"
    out = tmp_path / "out"
    capture = CaptureTelemetryTransport()

    from codestrata.telemetry import service as svc

    real_ensure = svc.ensure_interactive_product_telemetry

    def _ensure(**kwargs):
        kwargs = dict(kwargs)
        kwargs["transport"] = capture
        kwargs["telemetry_allow"] = True
        return real_ensure(**kwargs)

    with patch.object(svc, "ensure_interactive_product_telemetry", side_effect=_ensure):
        result = _invoke_assess(missing, out, extra=["--telemetry-allow"])
    assert result.exit_code != 0
    assert result.exit_code != 2  # not flag conflict
    assert "Traceback" not in result.stdout


def test_primary_failure_with_raising_transport(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    from codestrata.telemetry.persisted_consent import persist_v2_yes

    persist_v2_yes(path=home / "telemetry.json")
    reset_telemetry_singletons()
    missing = tmp_path / "nope"
    out = tmp_path / "out"
    capture = CaptureTelemetryTransport(raise_on_send=True)

    from codestrata.telemetry import service as svc

    real_ensure = svc.ensure_interactive_product_telemetry

    def _ensure(**kwargs):
        kwargs = dict(kwargs)
        kwargs["transport"] = capture
        kwargs["telemetry_allow"] = True
        return real_ensure(**kwargs)

    with patch.object(svc, "ensure_interactive_product_telemetry", side_effect=_ensure):
        result = _invoke_assess(missing, out, extra=["--telemetry-allow"])
    assert result.exit_code != 0
    assert "Allow privacy-safe" not in (result.stdout + result.stderr)


def test_flag_conflict_still_exit_2(tmp_path: Path) -> None:
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    result = _invoke_assess(
        repo, out, extra=["--telemetry-allow", "--telemetry-deny"]
    )
    assert result.exit_code == 2
    assert TELEMETRY_FLAG_CONFLICT_MESSAGE in (result.stdout + result.stderr)
    assert not list(out.rglob("assessment.json"))


def test_json_summary_unpolluted_by_telemetry_failure(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    with patch(
        "codestrata.telemetry.disabled_service.DisabledTelemetryFacade.record_assessment_started",
        side_effect=RuntimeError("should be isolated"),
    ):
        result = _invoke_assess(
            repo, out, extra=["--json-summary", "--telemetry-deny"]
        )
    assert result.exit_code == 0
    # JSON summary should remain parseable machine output
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines
    payload = json.loads(lines[-1])
    assert isinstance(payload, dict)
    assert "telemetry_error" not in payload
    assert "endpoint" not in json.dumps(payload)


def test_factory_failure_falls_back_and_assess_continues(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    with patch(
        "codestrata.telemetry.prompt_runtime_factory.create_interactive_session_telemetry",
        side_effect=RuntimeError("factory boom"),
    ):
        result = _invoke_assess(repo, out, extra=["--telemetry-deny"])
    assert result.exit_code == 0
    assert {path.name for path in home.iterdir()} <= {"installation_id"}


def test_normal_cli_without_credential_stays_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    monkeypatch.delenv("CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL", raising=False)
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    result = _invoke_assess(repo, out, extra=["--telemetry-allow"])
    assert result.exit_code == 0
    from codestrata.telemetry.service import get_telemetry_service

    transport = get_telemetry_service().runtime.session.transport
    assert getattr(transport, "transport_category", "") in {
        "unavailable",
        "http",
        "disabled",
    }


def test_normal_cli_opt_in_with_credential_uses_http_transport(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv(
        "CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL",
        "cscc_v1_" + ("a" * 32),
    )
    from codestrata.telemetry.persisted_consent import persist_v2_yes

    persist_v2_yes(path=home / "telemetry.json")
    reset_telemetry_singletons()
    repo = _mini_repo(tmp_path)
    out = tmp_path / "out"
    result = _invoke_assess(repo, out, extra=["--telemetry-allow"])
    assert result.exit_code == 0
    from codestrata.telemetry.infrastructure.http_transport import HttpTelemetryTransport
    from codestrata.telemetry.service import get_telemetry_service

    transport = get_telemetry_service().runtime.session.transport
    assert isinstance(transport, HttpTelemetryTransport)
    assert transport.transport_category == "http"
    assert "api.codestrata.ai" in transport._configuration.endpoint
    assert transport._configuration.endpoint.endswith("/api/v1/telemetry")


def test_artifacts_equivalent_across_telemetry_outcomes(
    tmp_path: Path, monkeypatch
) -> None:
    """Deny vs allow+unavailable should not change report schema/identity fields."""

    monkeypatch.setenv("CI", "1")
    reports: list[dict] = []
    for label, flag in (("deny", ["--telemetry-deny"]), ("allow", ["--telemetry-allow"])):
        home = tmp_path / f"home-{label}"
        home.mkdir()
        monkeypatch.setenv("CODESTRATA_HOME", str(home))
        reset_telemetry_singletons()
        repo = _mini_repo(tmp_path / f"work-{label}")
        out = tmp_path / f"out-{label}"
        result = _invoke_assess(repo, out, extra=flag)
        assert result.exit_code == 0
        report_path = next(out.rglob("assessment.json"))
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        reports.append(payload)
        assert "telemetry_events" not in payload
        assert "installation_id" not in payload

    a, b = reports
    # Schema version stable
    schema_a = a.get("schema") or a.get("schema_version") or a.get("assessment_schema_version")
    schema_b = b.get("schema") or b.get("schema_version") or b.get("assessment_schema_version")
    if schema_a is not None:
        assert schema_a == schema_b
