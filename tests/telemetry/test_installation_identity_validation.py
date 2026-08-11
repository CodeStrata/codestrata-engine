"""Anonymous installation identity validation and compatibility tests (Slice 10.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    diagnose_anonymous_installation_identity,
    is_uuid_v4,
    new_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.installation_identity_compatibility import (
    InstallationIdentityCompatibilityError,
    assert_identity_schema_compatible,
    compatible_identity_schema_versions,
    migrate_identity_mapping,
)
from codestrata.telemetry.analytics.installation_identity_errors import (
    InstallationIdentityError,
    InstallationIdentityErrorCode,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID,
    IDENTITY_FILENAME,
    InstallationIdentityPolicyError,
    CommunityAnonymousInstallationIdentityPolicy,
)
from codestrata.telemetry.analytics.installation_identity_serialization import (
    identity_policy_to_stable_json,
    identity_to_stable_json,
)
from codestrata.telemetry.analytics.installation_identity_storage import (
    write_identity_atomic,
)
from codestrata.telemetry.analytics.installation_identity_validation import (
    parse_identity_bytes,
    parse_identity_mapping,
    validate_identity_record,
)


def _valid_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "installation_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        "policy_version": "1.0",
        "schema_id": COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID,
        "schema_version": "1.0",
    }
    base.update(overrides)
    return base


def test_parse_valid_mapping() -> None:
    record = parse_identity_mapping(_valid_payload())
    assert record.installation_id == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    assert is_uuid_v4(record.installation_id)


def test_canonicalizes_uuid_case() -> None:
    record = parse_identity_mapping(
        _valid_payload(installation_id="AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE")
    )
    assert record.installation_id == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({}, InstallationIdentityErrorCode.CORRUPT_RECORD),
        (
            _valid_payload(installation_id="not-a-uuid"),
            InstallationIdentityErrorCode.INVALID_IDENTIFIER,
        ),
        (
            _valid_payload(installation_id="aaaaaaaa-bbbb-3ccc-8ddd-eeeeeeeeeeee"),
            InstallationIdentityErrorCode.INVALID_IDENTIFIER,
        ),
        (
            _valid_payload(schema_version="9.9"),
            InstallationIdentityErrorCode.UNSUPPORTED_SCHEMA,
        ),
        (
            _valid_payload(schema_id="other-schema"),
            InstallationIdentityErrorCode.UNSUPPORTED_SCHEMA,
        ),
        (
            _valid_payload(policy_version="9.9"),
            InstallationIdentityErrorCode.UNSUPPORTED_POLICY,
        ),
        (
            {**_valid_payload(), "extra": "x"},
            InstallationIdentityErrorCode.CORRUPT_RECORD,
        ),
    ],
)
def test_rejects_invalid_mappings(
    payload: dict[str, object], code: InstallationIdentityErrorCode
) -> None:
    with pytest.raises(InstallationIdentityError) as exc:
        parse_identity_mapping(payload)
    assert exc.value.code is code
    assert payload.get("installation_id", "sentinel") == payload.get(
        "installation_id", "sentinel"
    )
    # Error message is the code value only — no payload echo.
    assert str(exc.value) == code.value


def test_malformed_bytes_rejected() -> None:
    with pytest.raises(InstallationIdentityError) as exc:
        parse_identity_bytes(b"{not-json")
    assert exc.value.code is InstallationIdentityErrorCode.CORRUPT_RECORD


def test_non_object_json_rejected() -> None:
    with pytest.raises(InstallationIdentityError) as exc:
        parse_identity_bytes(b'["x"]')
    assert exc.value.code is InstallationIdentityErrorCode.CORRUPT_RECORD


def test_validate_identity_record_round_trip() -> None:
    record = new_anonymous_installation_identity()
    assert validate_identity_record(record) == record


def test_compatibility_matrix() -> None:
    assert compatible_identity_schema_versions() == frozenset({"1.0"})
    assert_identity_schema_compatible("1.0")
    with pytest.raises(InstallationIdentityCompatibilityError):
        assert_identity_schema_compatible("2.0")


def test_migrate_identity_mapping_noop_for_1_0() -> None:
    payload = _valid_payload()
    assert migrate_identity_mapping(payload) == payload


def test_deterministic_serialization() -> None:
    record = AnonymousInstallationIdentity(
        installation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )
    a = identity_to_stable_json(record)
    b = identity_to_stable_json(record)
    assert a == b
    parsed = json.loads(a)
    assert list(parsed.keys()) == sorted(parsed.keys())
    policy_a = identity_policy_to_stable_json(
        CommunityAnonymousInstallationIdentityPolicy.default()
    )
    policy_b = identity_policy_to_stable_json(
        CommunityAnonymousInstallationIdentityPolicy.default()
    )
    assert policy_a == policy_b


def test_unsupported_policy_construction() -> None:
    with pytest.raises(InstallationIdentityPolicyError):
        CommunityAnonymousInstallationIdentityPolicy(transmission_allowed=True)
    with pytest.raises(InstallationIdentityPolicyError):
        CommunityAnonymousInstallationIdentityPolicy(regenerate_automatically=True)
    with pytest.raises(InstallationIdentityPolicyError):
        CommunityAnonymousInstallationIdentityPolicy(machine_fingerprint_allowed=True)


def test_diagnose_corrupt_file_no_id_leak(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    secret = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    (home / IDENTITY_FILENAME).write_text(
        json.dumps({"installation_id": secret, "broken": True}),
        encoding="utf-8",
    )
    diag = diagnose_anonymous_installation_identity(home=home)
    assert diag.identity_present is True
    assert diag.identity_valid is False
    assert diag.last_error_code is not None
    blob = diag.to_stable_json()
    assert secret not in blob
    assert str(home) not in blob
    assert "installation_id" not in diag.to_stable_dict()


def test_atomic_write_round_trip(tmp_path: Path) -> None:
    path = tmp_path / IDENTITY_FILENAME
    record = new_anonymous_installation_identity()
    write_identity_atomic(record, path=path)
    loaded = parse_identity_bytes(path.read_bytes())
    assert loaded == record
