"""Deterministic identifiers and fingerprints for knowledge artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from codestrata.domain.graph.validation import require_nonblank


def _stable_json(payload: Mapping[str, Any]) -> str:
    """Serialize a mapping with byte-stable formatting (sorted keys)."""

    return (
        json.dumps(
            dict(payload),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def content_hash(content: str) -> str:
    """Return a stable SHA-256 content digest (``sha256:`` prefixed)."""

    text = require_nonblank(content, label="content")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def fingerprint_payload(payload: Mapping[str, Any]) -> str:
    """Fingerprint a JSON-compatible mapping with stable serialization."""

    text = _stable_json(payload)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def build_document_id(
    *,
    source_type: str,
    source_id: str,
    content_digest: str,
) -> str:
    """Build a deterministic knowledge document identity."""

    source = require_nonblank(source_type, label="source_type").strip().lower()
    sid = require_nonblank(source_id, label="source_id")
    digest = require_nonblank(content_digest, label="content_digest")
    material = f"knowledge-document\n{source}\n{sid}\n{digest}"
    token = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"kd:{token}"


def build_chunk_id(
    *,
    document_id: str,
    sequence: int,
    content_digest: str,
) -> str:
    """Build a deterministic knowledge chunk identity."""

    doc = require_nonblank(document_id, label="document_id")
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    digest = require_nonblank(content_digest, label="content_digest")
    material = f"knowledge-chunk\n{doc}\n{sequence}\n{digest}"
    token = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"kc:{token}"


def build_vector_record_id(
    *,
    namespace: str,
    entity_id: str,
) -> str:
    """Build a deterministic vector-record identity for upserts."""

    ns = require_nonblank(namespace, label="namespace").strip().lower()
    entity = require_nonblank(entity_id, label="entity_id")
    material = f"vector-record\n{ns}\n{entity}"
    token = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"vr:{token}"
