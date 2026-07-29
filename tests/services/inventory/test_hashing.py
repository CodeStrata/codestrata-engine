"""Tests for inventory content hashing."""

from __future__ import annotations

from codestrata.domain.repository import HashAlgorithm, hash_bytes
from codestrata.services.inventory import ContentHashingService


def test_content_hashing_service_uses_sha256_by_default() -> None:
    service = ContentHashingService()
    fingerprint = service.fingerprint(b"hello")
    assert fingerprint.algorithm is HashAlgorithm.SHA256
    assert fingerprint == hash_bytes(b"hello", algorithm=HashAlgorithm.SHA256)
    assert fingerprint != service.fingerprint(b"hello!")


def test_content_hashing_is_deterministic() -> None:
    service = ContentHashingService(HashAlgorithm.SHA256)
    assert service.fingerprint(b"same") == service.fingerprint(b"same")
