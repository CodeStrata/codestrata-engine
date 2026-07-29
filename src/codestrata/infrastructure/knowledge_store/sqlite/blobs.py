"""Content-addressed immutable JSON blob storage."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any
from uuid import uuid4

from codestrata.application.knowledge.errors import (
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
)
from codestrata.application.knowledge.models import KnowledgeArtifactKind
from codestrata.infrastructure.knowledge_store.defaults import BLOB_KIND_DIRECTORIES
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


class BlobStore:
    """Write and read content-addressed JSON blobs under the knowledge root."""

    def __init__(self, knowledge_root: Path, blobs_directory: Path, tmp_directory: Path) -> None:
        self._root = knowledge_root.resolve()
        self._blobs = blobs_directory
        self._tmp = tmp_directory

    def write_json_blob(
        self,
        kind: KnowledgeArtifactKind,
        payload: dict[str, Any] | list[Any],
    ) -> tuple[str, str]:
        """Persist payload; return ``(relative_blob_ref, sha256_hex)``."""

        text = dumps_stable_json(payload)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        relative = self._relative_ref(kind, digest)
        absolute = self._resolve_ref(relative)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        if absolute.exists():
            existing = absolute.read_bytes()
            existing_digest = hashlib.sha256(existing).hexdigest()
            if existing_digest != digest:
                raise KnowledgeStoreCorruptionError(
                    f"Blob hash collision or corruption at {relative}"
                )
            return relative, digest

        tmp_path = self._tmp / f"{uuid4().hex}.json"
        self._tmp.mkdir(parents=True, exist_ok=True)
        try:
            tmp_path.write_text(text, encoding="utf-8")
            try:
                os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
            with tmp_path.open("rb") as handle:
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(tmp_path, absolute)
            try:
                os.chmod(absolute, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
        return relative, digest

    def read_json_blob(self, blob_ref: str, *, expected_hash: str) -> Any:
        """Read and verify a blob, returning the parsed JSON payload."""

        absolute = self._resolve_ref(blob_ref)
        if not absolute.is_file():
            raise KnowledgeStoreCorruptionError(f"Missing blob: {blob_ref}")
        raw = absolute.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_hash:
            raise KnowledgeStoreCorruptionError(
                f"Blob hash mismatch for {blob_ref}: expected {expected_hash}, got {digest}"
            )
        try:
            return loads_stable_json(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise KnowledgeStoreCorruptionError(
                f"Malformed JSON blob: {blob_ref}"
            ) from error

    def cleanup_tmp(self) -> int:
        """Remove leftover temporary files; return count deleted."""

        if not self._tmp.is_dir():
            return 0
        deleted = 0
        for path in self._tmp.iterdir():
            if path.is_file():
                try:
                    path.unlink()
                    deleted += 1
                except OSError:
                    continue
        return deleted

    def _relative_ref(self, kind: KnowledgeArtifactKind, digest: str) -> str:
        directory = BLOB_KIND_DIRECTORIES.get(kind.value, "misc")
        return f"blobs/{directory}/{digest}.json"

    def _resolve_ref(self, blob_ref: str) -> Path:
        compact = blob_ref.strip().replace("\\", "/")
        if not compact or compact.startswith("/") or ".." in compact.split("/"):
            raise KnowledgeStoreError(f"Illegal blob reference: {blob_ref}")
        if not compact.startswith("blobs/"):
            raise KnowledgeStoreError(f"Blob reference must be under blobs/: {blob_ref}")
        absolute = (self._root / compact).resolve()
        try:
            absolute.relative_to(self._root)
        except ValueError as error:
            raise KnowledgeStoreError(
                f"Blob reference escapes knowledge root: {blob_ref}"
            ) from error
        return absolute
