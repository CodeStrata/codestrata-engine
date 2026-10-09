"""E13.2 scoped JSON export serialization and negative fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.domain.contracts.serialization import PLACEHOLDER_DIGEST, digest_canonical
from codestrata.telemetry.export_models import (
    EXPORT_NOTICE,
    ExportCategory,
    ExportEnvelopeError,
    ScopedExportEnvelope,
    ServerReadiness,
)
from codestrata.telemetry.export_policy import EVIDENCE_EXPORT_SCHEMA, GRAPH_EXPORT_SCHEMA
from codestrata.telemetry.export_serialize import build_scoped_export, parse_scoped_export

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "export"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_good_evidence_and_graph_envelopes_bind_schema_digest_notice_category() -> None:
    evidence = parse_scoped_export(_load("good-evidence.json"))
    graph = parse_scoped_export(_load("good-graph.json"))
    for envelope, schema, category in (
        (evidence, EVIDENCE_EXPORT_SCHEMA, ExportCategory.EVIDENCE.value),
        (graph, GRAPH_EXPORT_SCHEMA, ExportCategory.GRAPH.value),
    ):
        assert envelope.schema == schema
        assert envelope.category == category
        assert envelope.notice == EXPORT_NOTICE
        assert envelope.digest == digest_canonical(envelope.content_slice())
        assert envelope.artifact_digest == PLACEHOLDER_DIGEST
        assert envelope.transmission_performed is False
        assert envelope.server_readiness == ServerReadiness.NOT_READY.value
        assert "findings" not in envelope.to_stable_dict()
        assert "snippet" not in envelope.to_stable_dict()
        assert "repository_name" not in envelope.to_stable_dict()
        assert envelope.to_stable_dict()["server_readiness"] == "not_ready"


def test_preview_is_deterministic() -> None:
    first = build_scoped_export(ExportCategory.EVIDENCE).to_stable_json()
    second = build_scoped_export("evidence").to_stable_json()
    assert first == second


def test_negative_and_partial_fixtures_are_rejected() -> None:
    with pytest.raises(ExportEnvelopeError):
        parse_scoped_export(_load("missing-digest.json"))
    with pytest.raises(ExportEnvelopeError):
        parse_scoped_export(_load("unsupported-schema.json"))
    with pytest.raises(ExportEnvelopeError):
        parse_scoped_export(_load("unsupported-category.json"))
    with pytest.raises(ExportEnvelopeError):
        parse_scoped_export(_load("unsupported-major.json"))
    with pytest.raises(ExportEnvelopeError, match="prohibited or unknown"):
        parse_scoped_export(_load("prohibited-fields.json"))
    with pytest.raises(ExportEnvelopeError, match="prohibited or unknown"):
        parse_scoped_export(_load("partial-unknown-field.json"))
    with pytest.raises(json.JSONDecodeError):
        json.loads((FIXTURE_DIR / "corrupt.json").read_text(encoding="utf-8"))


def test_budget_failure_on_oversized_export() -> None:
    from codestrata.telemetry.export_policy import EngineCollectionExportPolicy

    tiny = EngineCollectionExportPolicy(max_export_size_bytes=64)
    with pytest.raises(ExportEnvelopeError, match="maximum size"):
        build_scoped_export(ExportCategory.GRAPH, policy=tiny)


def test_invalid_category_rejected() -> None:
    with pytest.raises(ExportEnvelopeError, match="unsupported export category"):
        build_scoped_export("lake")


def test_existing_envelope_is_revalidated() -> None:
    envelope = build_scoped_export(ExportCategory.EVIDENCE)
    again = parse_scoped_export(envelope)
    assert again.digest == envelope.digest
    broken = ScopedExportEnvelope(
        schema=envelope.schema,
        schema_version=envelope.schema_version,
        category=envelope.category,
        digest="0" * 64,
        notice=envelope.notice,
        artifact_digest=envelope.artifact_digest,
    )
    with pytest.raises(ExportEnvelopeError, match="digest does not match"):
        parse_scoped_export(broken)
