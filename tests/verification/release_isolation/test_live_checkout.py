"""Live checkout: ci.yml covers release/** and ordinary merges do not publish."""

from __future__ import annotations

from pathlib import Path

from verification.release_isolation.inspect import inspect_checkout
from verification.release_isolation.models import CheckStatus
from verification.release_isolation.render import render_isolation

REPO = Path(__file__).resolve().parents[4]


def test_live_ci_push_covers_release_glob() -> None:
    inspection = inspect_checkout(REPO)
    assert inspection.push.status is CheckStatus.PASS
    assert inspection.push.covers_required_glob
    assert "release/**" in inspection.push.patterns
    assert inspection.ordinary_merge.status is CheckStatus.PASS
    assert inspection.status is CheckStatus.PASS
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert '"release/**"' in ci
    assert "contents: read" in ci


def test_rendered_doc_names_lanes_and_namespaces() -> None:
    text = render_isolation(inspect_checkout(REPO))
    assert "release/engine-next" in text
    assert "main" in text
    assert ".venv-engine-next" in text
    assert "engine/.tmp-assess/engine-next-candidate/" in text
    assert "a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18" in text


def test_checked_in_doc_matches_renderer() -> None:
    expected = render_isolation(inspect_checkout(REPO))
    actual = (REPO / "engine" / "docs" / "release" / "isolation.md").read_text(encoding="utf-8")
    assert actual == expected


def test_determinism_three_repeats() -> None:
    first = inspect_checkout(REPO)
    second = inspect_checkout(REPO)
    third = inspect_checkout(REPO)
    assert first.push.patterns == second.push.patterns == third.push.patterns
    assert first.status == second.status == third.status
    assert first.ordinary_merge.status == third.ordinary_merge.status
