"""SHA-256 helpers for assessment artifact publishing."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> tuple[str, int, bytes]:
    content = path.read_bytes()
    return sha256_hex(content), len(content), content
