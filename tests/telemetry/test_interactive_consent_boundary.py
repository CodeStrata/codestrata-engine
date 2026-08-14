"""Boundary negatives for interactive consent (Slice 9.4)."""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata.telemetry.consent import allow_session_consent_from_interactive_prompt
from codestrata.telemetry.interactive_consent import (
    PROMPT_INTRO,
    PROMPT_QUESTION,
    run_interactive_consent_prompt,
)
from codestrata.telemetry.prompt_runtime_factory import create_interactive_session_telemetry
from codestrata.telemetry.projection import project_from_mapping
from codestrata.telemetry.errors import TelemetryRuntimeError
import pytest


TELEMETRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


@pytest.fixture(autouse=True)
def _isolate_codestrata_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep persisted consent out of the developer/runner ~/.codestrata."""

    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path))


def test_Q_consent_cannot_bypass_privacy() -> None:
    with pytest.raises(TelemetryRuntimeError):
        project_from_mapping(
            {
                "event_type": "application_started",
                "client_name": "codestrata_cli",
                "repository_name": "acme",
            }
        )
    allow = allow_session_consent_from_interactive_prompt()
    assert allow.transmission_authorized is True


def test_R_S_prompt_text_has_no_repo_or_raw_event() -> None:
    blob = (PROMPT_INTRO + PROMPT_QUESTION).lower()
    for needle in ("/users/", "argv", "endpoint", "stack trace", "repository/"):
        assert needle not in blob
    assert "help improve codestrata" in blob
    assert "anonymous usage" in blob
    assert "assessment insights" in blob
    assert "source code" in blob and ("stay local" in blob or "local" in blob)
    assert "repository identity" in blob
    assert "does not publish reports" in blob
    assert "score" not in blob
    assert "[y/n]" in blob
    assert "[Y/n]" not in (PROMPT_INTRO + PROMPT_QUESTION)


def test_U_piped_non_interactive_does_not_allow() -> None:
    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
        input_func=lambda _p: "y",
        echo_func=lambda _m: None,
    )
    assert result.prompted is False
    assert result.attempts == 0
    assert result.decision == "non_interactive_disabled"
    assert result.decision_source == "non_interactive_policy"


def test_V_answer_not_stored_in_result() -> None:
    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "yes-secret-answer",
        echo_func=lambda _m: None,
    )
    assert "yes-secret-answer" not in result.to_stable_json()
    assert "secret" not in result.to_stable_json()


def test_Y_allowed_unavailable_not_sent(monkeypatch) -> None:
    # Keep unit test isolated from any local Community client credential.
    monkeypatch.setattr(
        "codestrata.telemetry.product_transport.try_create_production_http_transport",
        lambda: None,
    )
    facade, result = create_interactive_session_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "y",
        echo_func=lambda _m: None,
    )
    assert result.decision == "allowed_for_session"
    from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent

    recorded = facade.runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert recorded.transport_kind == "unavailable"


def test_Z_prompt_result_deterministic_ordering() -> None:
    a = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "n",
        echo_func=lambda _m: None,
    )
    b = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "n",
        echo_func=lambda _m: None,
    )
    assert a.to_stable_json() == b.to_stable_json()
    assert list(a.to_stable_dict().keys()) == sorted(a.to_stable_dict().keys())


def test_no_platform_datalake_imports() -> None:
    forbidden = ("codestrata_platform", "codestrata_platform.community_cloud","community_cloud_api", "boto3", "fastapi", "data_lake")
    for path in TELEMETRY_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for needle in forbidden:
                    assert needle not in (name or ""), f"{path}: {name}"
