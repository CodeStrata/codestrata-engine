"""Product path must not create or flush the legacy local queue."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_E_F_no_queue_create_or_flush(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    queue = home / "telemetry-queue.jsonl"
    queue.write_text(
        json.dumps({"event": "assessment_started", "schema_version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    before = queue.read_text(encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.queue.enqueue") as enq:
        with patch("codestrata.telemetry.queue.load_queue") as load:
            with patch("codestrata.telemetry.queue.replace_queue") as replace:
                facade = get_telemetry_service()
                facade.record_assessment_started(ai_enabled=False)
                facade.emit("assessment_completed", command="assess")
                assert facade.flush_queue() == 0
                enq.assert_not_called()
                load.assert_not_called()
                replace.assert_not_called()

    assert queue.read_text(encoding="utf-8") == before
