"""Release metadata: package version surfaces stay aligned (no PyPI inference)."""

from __future__ import annotations

import re
from pathlib import Path

from codestrata import __version__


def test_init_version_matches_pyproject() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None
    assert __version__ == match.group(1)
