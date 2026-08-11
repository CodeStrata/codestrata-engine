"""Tests for the generic CLI > environment > file > default precedence helper."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.configuration_precedence import (
    FIELD_PRECEDENCE_NOTES,
    PRECEDENCE_ORDER,
    select_first_present,
)
from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError


def test_precedence_order_is_cli_env_file_default() -> None:
    assert PRECEDENCE_ORDER == (
        SourceCategory.CLI,
        SourceCategory.ENVIRONMENT,
        SourceCategory.CONFIGURATION_FILE,
        SourceCategory.DEFAULT,
    )


def test_select_first_present_prefers_cli_over_everything() -> None:
    value, source = select_first_present(
        candidates=(
            ("cli-value", SourceCategory.CLI),
            ("env-value", SourceCategory.ENVIRONMENT),
            ("file-value", SourceCategory.CONFIGURATION_FILE),
        ),
        default="default-value",
    )
    assert (value, source) == ("cli-value", SourceCategory.CLI)


def test_select_first_present_skips_blank_and_none_candidates() -> None:
    value, source = select_first_present(
        candidates=(
            (None, SourceCategory.CLI),
            ("   ", SourceCategory.ENVIRONMENT),
            ("file-value", SourceCategory.CONFIGURATION_FILE),
        ),
        default="default-value",
    )
    assert (value, source) == ("file-value", SourceCategory.CONFIGURATION_FILE)


def test_select_first_present_falls_back_to_default() -> None:
    value, source = select_first_present(
        candidates=((None, SourceCategory.CLI),),
        default="default-value",
    )
    assert (value, source) == ("default-value", SourceCategory.DEFAULT)


def test_select_first_present_rejects_blank_default() -> None:
    with pytest.raises(ProviderContractValidationError):
        select_first_present(candidates=(), default="   ")


def test_field_precedence_notes_cover_model_and_provider() -> None:
    assert "provider_id" in FIELD_PRECEDENCE_NOTES
    assert "model_reference" in FIELD_PRECEDENCE_NOTES
    assert "no --provider" in FIELD_PRECEDENCE_NOTES["provider_id"]


def test_field_precedence_notes_document_env_overlay_asymmetry() -> None:
    note = FIELD_PRECEDENCE_NOTES["model_reference"]
    assert "CODESTRATA_OPENAI_MODEL_ID" in note
    assert "CODESTRATA_BEDROCK_MODEL_ID" in note
    assert "not overlaid into settings" in note
