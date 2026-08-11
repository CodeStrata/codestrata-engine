"""Product path must not generate or read installation identity."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.prompt import maybe_prompt_telemetry_opt_in
from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_C_D_no_installation_id_on_product_path(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    existing = home / "installation_id"
    existing.write_text("11111111-1111-4111-8111-111111111111\n", encoding="utf-8")
    before = existing.read_text(encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.identity.ensure_installation_id") as ensure:
        with patch("codestrata.telemetry.identity.read_installation_id") as read:
            maybe_prompt_telemetry_opt_in()
            facade = get_telemetry_service()
            assert facade.ensure_identity() == ("", False)
            facade.record_assessment_started(ai_enabled=False)
            status = facade.status()
            assert "installation_id" not in status
            ensure.assert_not_called()
            read.assert_not_called()

    assert existing.read_text(encoding="utf-8") == before
    assert list(home.iterdir()) == [existing]


def test_absence_of_identity_does_not_create_file(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_telemetry_service().record_report_opened()
    assert list(home.iterdir()) == []
