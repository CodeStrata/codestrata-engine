"""HTML Recommendation Confidence presentation (Slice 5.5)."""

from __future__ import annotations

from codestrata.reporting.html_v2.models import RecommendationView
from codestrata.reporting.html_v2.renderer import _render_recommendation_card


def test_recommendation_card_shows_explicit_recommendation_confidence() -> None:
    item = RecommendationView(
        recommendation_id="rec-1",
        title="Harden authentication",
        summary="summary",
        rationale="rationale",
        priority="high",
        category="security",
        related_finding_ids=("f1",),
        related_finding_titles=("Secret finding",),
        primary_finding_id="f1",
        recommendation_type="finding_backed",
        evidence_completeness="complete",
        recommendation_confidence_level="moderate",
        limitations=("Mixed Finding Confidence among supporting findings.",),
        actions=(),
    )
    html = _render_recommendation_card(item, compact=False)
    assert "Recommendation confidence" in html
    assert "Moderate" in html
    assert "Horizon" in html
    assert "Finding confidence" not in html
