"""Process-local session isolation via subprocess (Slice 9.3)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = r"""
import json
import sys
from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.runtime_factory import (
    create_default_telemetry_runtime,
    create_session_telemetry_runtime,
)

mode = sys.argv[1]
if mode == "allow":
    capture = CaptureTelemetryTransport()
    rt = create_session_telemetry_runtime(consent=allow_session_consent(), transport=capture)
    rt.record(RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED))
    print(json.dumps({
        "decision": rt.session.decision.value,
        "captured": len(capture.captured),
        "authorized": rt.session.transmission_authorized,
    }))
elif mode == "default":
    capture = CaptureTelemetryTransport()
    rt = create_default_telemetry_runtime(transport=capture)
    rt.record(RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED))
    print(json.dumps({
        "decision": rt.session.decision.value,
        "captured": len(capture.captured),
        "authorized": rt.session.transmission_authorized,
    }))
else:
    raise SystemExit(2)
"""


def test_D_subprocess_consent_not_reused(tmp_path: Path) -> None:
    script = tmp_path / "consent_probe.py"
    script.write_text(SCRIPT, encoding="utf-8")
    env_home = tmp_path / "home"
    env_home.mkdir()
    env = {
        **dict(**{k: v for k, v in __import__("os").environ.items()}),
        "CODESTRATA_HOME": str(env_home),
        "CODESTRATA_TELEMETRY": "1",
        "CODESTRATA_TELEMETRY_ENDPOINT": "https://example.invalid/t",
        "PYTHONPATH": str(
            Path(__file__).resolve().parents[2] / "src"
        ),
    }
    # Prefer repo venv python if available via sys.executable.
    allow = subprocess.run(
        [sys.executable, str(script), "allow"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    default = subprocess.run(
        [sys.executable, str(script), "default"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    import json

    allow_payload = json.loads(allow.stdout.strip())
    default_payload = json.loads(default.stdout.strip())
    assert allow_payload["decision"] == "allowed_for_session"
    assert allow_payload["captured"] == 1
    assert default_payload["decision"] == "disabled_by_default"
    assert default_payload["captured"] == 0
    assert default_payload["authorized"] is False
    # No consent file written between processes.
    assert list(env_home.iterdir()) == []
