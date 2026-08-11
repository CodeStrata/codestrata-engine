"""Anonymous installation identity lifecycle tests (Epic 10 Slice 10.2)."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from codestrata.telemetry.analytics.installation_identity import (
    diagnose_anonymous_installation_identity,
    ensure_anonymous_installation_identity,
    generate_anonymous_installation_id,
    is_uuid_v4,
    load_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.installation_identity_errors import (
    InstallationIdentityError,
    InstallationIdentityErrorCode,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    IDENTITY_FILENAME,
    CommunityAnonymousInstallationIdentityPolicy,
    default_installation_identity_policy,
)
from codestrata.telemetry.analytics.installation_identity_storage import (
    installation_identity_path,
)


def test_first_generation_persists_and_reloads(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first, created, recovered = ensure_anonymous_installation_identity(home=home)
    assert created is True
    assert recovered is False
    assert is_uuid_v4(first.installation_id)
    assert (home / IDENTITY_FILENAME).is_file()

    second, created2, recovered2 = ensure_anonymous_installation_identity(home=home)
    assert created2 is False
    assert recovered2 is False
    assert second.installation_id == first.installation_id

    loaded = load_anonymous_installation_identity(home=home)
    assert loaded is not None
    assert loaded.installation_id == first.installation_id


def test_does_not_regenerate_valid_identity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    original, _, _ = ensure_anonymous_installation_identity(home=home)
    for _ in range(5):
        again, created, recovered = ensure_anonymous_installation_identity(home=home)
        assert created is False
        assert recovered is False
        assert again.installation_id == original.installation_id


def test_independent_from_legacy_installation_id_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    legacy = home / "installation_id"
    legacy.write_text("11111111-1111-4111-8111-111111111111\n", encoding="utf-8")
    record, created, _ = ensure_anonymous_installation_identity(home=home)
    assert created is True
    assert record.installation_id != "11111111-1111-4111-8111-111111111111"
    assert legacy.read_text(encoding="utf-8").strip() == (
        "11111111-1111-4111-8111-111111111111"
    )


def test_independent_from_telemetry_preferences(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    prefs = home / "telemetry.json"
    prefs.write_text('{"enabled": true}\n', encoding="utf-8")
    ensure_anonymous_installation_identity(home=home)
    assert prefs.read_text(encoding="utf-8") == '{"enabled": true}\n'


def test_corruption_recovery_when_allowed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = installation_identity_path(home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    record, created, recovered = ensure_anonymous_installation_identity(home=home)
    assert created is True
    assert recovered is True
    assert is_uuid_v4(record.installation_id)
    reloaded = load_anonymous_installation_identity(home=home)
    assert reloaded is not None
    assert reloaded.installation_id == record.installation_id


def test_corruption_rejects_when_recovery_disabled(tmp_path: Path) -> None:
    home = tmp_path / "home"
    policy = replace(
        default_installation_identity_policy(),
        recover_on_corruption=False,
    )
    path = installation_identity_path(home=home, policy=policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(InstallationIdentityError) as exc:
        ensure_anonymous_installation_identity(home=home, policy=policy)
    assert exc.value.code is InstallationIdentityErrorCode.RECOVERY_DISABLED


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_anonymous_installation_identity(home=tmp_path / "empty") is None


def test_concurrent_reads_of_persisted_identity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    original, _, _ = ensure_anonymous_installation_identity(home=home)

    def _read() -> str:
        loaded = load_anonymous_installation_identity(home=home)
        assert loaded is not None
        return loaded.installation_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _read(), range(32)))
    assert set(results) == {original.installation_id}


def test_generate_is_random_uuid_v4() -> None:
    a = generate_anonymous_installation_id()
    b = generate_anonymous_installation_id()
    assert a != b
    assert is_uuid_v4(a)
    assert is_uuid_v4(b)


def test_persisted_json_is_stable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    record, _, _ = ensure_anonymous_installation_identity(home=home)
    raw = (home / IDENTITY_FILENAME).read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert list(payload.keys()) == sorted(payload.keys())
    assert payload["installation_id"] == record.installation_id


def test_diagnose_absent_and_present(tmp_path: Path) -> None:
    home = tmp_path / "home"
    absent = diagnose_anonymous_installation_identity(home=home)
    assert absent.identity_present is False
    assert absent.identity_valid is False
    assert absent.last_error_code is None
    ensure_anonymous_installation_identity(home=home)
    present = diagnose_anonymous_installation_identity(home=home)
    assert present.identity_present is True
    assert present.identity_valid is True


def test_default_policy_invariants() -> None:
    policy = default_installation_identity_policy()
    assert isinstance(policy, CommunityAnonymousInstallationIdentityPolicy)
    assert policy.transmission_allowed is False
    assert policy.telemetry_consent_coupled is False
    assert policy.regenerate_automatically is False
    assert policy.recover_on_corruption is True
    assert policy.machine_fingerprint_allowed is False
