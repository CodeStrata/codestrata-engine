"""E15.1 corpus manifests and E15.2 regression harness.

Maintainer-only: not part of the installed ``codestrata`` wheel.
"""

from __future__ import annotations

from verification.validation.checks import evaluate, overall_status
from verification.validation.loader import load_bundle
from verification.validation.models import CorpusBundle
from verification.validation.render import render_corpus

__all__ = [
    "CorpusBundle",
    "evaluate",
    "load_bundle",
    "overall_status",
    "render_corpus",
]
