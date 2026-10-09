"""E13.2 existing aggregate telemetry wire must stay findings-free."""

from __future__ import annotations

import pytest
from tests.telemetry.privacy_canaries import (
    PATH,
    REPO_NAME,
    assert_amd_1_1_allowlist,
    assert_no_canaries,
    canary_rich_projection_source,
)

from codestrata.telemetry.assessment_metadata.projector import (
    project_assessment_metadata,
)
from codestrata.telemetry.constants import ALLOWED_PAYLOAD_KEYS, FORBIDDEN_SUBSTRINGS
from codestrata.telemetry.validate import build_event_payload, validate_payload


def test_allowed_payload_keys_exclude_findings_snippets_repo_names() -> None:
    forbidden = {
        "findings",
        "finding",
        "snippet",
        "snippets",
        "repository_name",
        "repository_url",
        "source_code",
    }
    assert forbidden.isdisjoint(ALLOWED_PAYLOAD_KEYS)
    for needle in ("finding", "repository_name", "source_code"):
        assert needle in FORBIDDEN_SUBSTRINGS


def test_legacy_aggregate_payload_rejects_findings_and_repo_names() -> None:
    payload = build_event_payload(
        installation_id="11111111-1111-4111-8111-111111111111",
        event="assessment_completed",
        language_categories=["python"],
        repository_size_band="0-100",
        success=True,
    )
    assert "findings" not in payload
    assert "snippet" not in payload
    assert "repository_name" not in payload
    assert_no_canaries(payload)

    poisoned = dict(payload)
    poisoned["repository_name"] = REPO_NAME
    with pytest.raises(ValueError, match="disallowed payload key"):
        validate_payload(poisoned)
    poisoned = dict(payload)
    poisoned["findings"] = ["leak"]
    with pytest.raises(ValueError, match="disallowed payload key"):
        validate_payload(poisoned)
    poisoned = dict(payload)
    poisoned["snippet"] = PATH
    with pytest.raises(ValueError, match="disallowed payload key"):
        validate_payload(poisoned)


def test_assessment_metadata_aggregates_do_not_carry_canary_bodies() -> None:
    source = canary_rich_projection_source(
        assessment_id="11111111-2222-3333-4444-555555555555",
        installation_id="11111111-1111-4111-8111-111111111111",
    )
    payload = project_assessment_metadata(source).to_stable_dict()
    assert_amd_1_1_allowlist(payload)
    assert_no_canaries(payload)
    assert "snippet" not in payload
    assert "findings" not in payload
    assert payload.get("repository", {}).get("repository_name") is None
