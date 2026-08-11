"""Anonymous installation identity diagnostics and error taxonomy (Slice 10.2)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.telemetry.analytics.installation_identity import (
    diagnose_anonymous_installation_identity,
    ensure_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.installation_identity_diagnostics import (
    empty_installation_identity_diagnostics,
)
from codestrata.telemetry.analytics.installation_identity_errors import (
    InstallationIdentityError,
    InstallationIdentityErrorCode,
)
from codestrata.telemetry.analytics.installation_identity_policy import IDENTITY_FILENAME


def test_empty_diagnostics_are_bounded() -> None:
    diag = empty_installation_identity_diagnostics()
    payload = diag.to_stable_dict()
    assert payload["identity_present"] is False
    assert payload["transmission_allowed"] is False
    assert payload["telemetry_consent_coupled"] is False
    assert payload["last_error_code"] is None
    assert list(payload.keys()) == sorted(payload.keys())
    assert diag.to_stable_json() == json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def test_diagnostics_never_include_identifier(tmp_path: Path) -> None:
    home = tmp_path / "home"
    record, _, _ = ensure_anonymous_installation_identity(home=home)
    diag = diagnose_anonymous_installation_identity(home=home)
    blob = diag.to_stable_json()
    assert record.installation_id not in blob
    assert "installation_id" not in diag.to_stable_dict()
    assert str(home) not in blob


def test_diagnostics_corrupt_no_exception_text(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / IDENTITY_FILENAME).write_text("{oops", encoding="utf-8")
    diag = diagnose_anonymous_installation_identity(home=home)
    blob = diag.to_stable_json()
    assert diag.last_error_code == InstallationIdentityErrorCode.CORRUPT_RECORD.value
    assert "JSON" not in blob
    assert "oops" not in blob
    assert "Traceback" not in blob
    assert str(home) not in blob


def test_error_taxonomy_codes_are_stable() -> None:
    codes = {code.value for code in InstallationIdentityErrorCode}
    assert codes == {
        "validation_failed",
        "corrupt_record",
        "unsupported_schema",
        "unsupported_policy",
        "invalid_identifier",
        "persistence_failed",
        "recovery_disabled",
        "internal",
    }
    err = InstallationIdentityError(InstallationIdentityErrorCode.INTERNAL)
    assert str(err) == "internal"
    assert err.code is InstallationIdentityErrorCode.INTERNAL
