"""E13.3: no public private-data logging of secrets, findings, or repo names."""

from __future__ import annotations

import logging

import pytest
from tests.telemetry.privacy_canaries import PATH, REPO_NAME, SECRET, assert_no_canaries

from codestrata.domain.contracts.enums import ExportMode
from codestrata.telemetry.canaries import log_records_contain_prohibited
from codestrata.telemetry.export_projection_models import ProjectionEnvelopeError
from codestrata.telemetry.export_signing import assert_no_secret_leak
from codestrata.telemetry.signed_projection import build_original_package, project_export


def test_projection_manifest_and_logs_omit_private_data(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="codestrata.telemetry.signed_projection")
    original = build_original_package()
    _, projection = project_export(original, ExportMode.RESTRICTED, withheld_categories=("graph",))
    public = {
        "original": original.to_manifest_dict(),
        "projection": projection.to_manifest_dict(),
    }
    assert_no_canaries(public)
    blob = original.to_stable_json() + projection.to_stable_json()
    assert REPO_NAME not in blob
    assert PATH not in blob
    assert SECRET not in blob
    assert "not-for-production" not in blob
    hits = log_records_contain_prohibited(
        caplog.records,
        extra_needles=(SECRET, REPO_NAME, PATH),
    )
    assert hits == ()
    for record in caplog.records:
        rendered = record.getMessage()
        assert "not-for-production" not in rendered
        assert "hmac_key" not in rendered.lower()


def test_assert_no_secret_leak_rejects_private_fields() -> None:
    with pytest.raises(ProjectionEnvelopeError, match="signing secret"):
        assert_no_secret_leak(
            {"note": "codestrata-export-projection-test-key-not-for-production"}
        )
    with pytest.raises(ProjectionEnvelopeError, match="prohibited"):
        assert_no_secret_leak({"repository_name": REPO_NAME, "snippet": "x"})
    with pytest.raises(ProjectionEnvelopeError, match="private key"):
        assert_no_secret_leak({"hmac_key": "x"})
