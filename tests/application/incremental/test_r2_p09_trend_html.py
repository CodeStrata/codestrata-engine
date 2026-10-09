"""R2-P09 five-commit trend HTML projection."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.incremental.trend_bundle import (
    COMPARISON_NAMES,
    SLOT_NAMES,
    TREND_HTML_FILENAME,
)
from codestrata.application.incremental.trend_series import run_trend_series
from codestrata.reporting.engineering_health.trend_report import render_trend_html
from codestrata.reporting.html_v2.assessment_heads import engineering_health_outcome_title
from tests.application.incremental.test_r2_p06_trend_series import (
    LATER_PATH,
    _fake_assess_factory,
    _five_commit_adversarial,
    _settings,
)

PINNED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
HEADLINE_TITLES = (
    "Architecture",
    "Security",
    "Quality",
    "Maintainability & Technical Debt",
)


def _html_for_series(tmp_path: Path, *, fail_slot_sha: str | None = None) -> tuple[Path, str]:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([], fail_slot_sha=fail_slot_sha),
    )
    html = (series / TREND_HTML_FILENAME).read_text(encoding="utf-8")
    return series, html


def test_trend_html_projects_five_slots_and_pairs_without_score(tmp_path: Path) -> None:
    series, html = _html_for_series(tmp_path)
    assert "Five-commit health trend" in html
    assert "What changed across the five commits" in html
    assert "Current HEAD Engineering Health" in html
    assert "Oldest → HEAD" in html
    assert "Latest adjacent" in html
    assert "adjacent" in html
    assert "oldest to HEAD" in html
    for title in HEADLINE_TITLES:
        assert title.replace("&", "&amp;") in html
    for name in SLOT_NAMES:
        assert f"id=\"slot-{name}\"" in html
        assert f"id=\"evidence-{name}\"" in html
    for name in COMPARISON_NAMES:
        assert f"id=\"comparison-{name}\"" in html
    assert "health score" not in html.lower()
    assert "Architecture Intelligence" not in html
    assert "Security Intelligence" not in html
    offline = html.replace("https://github.com/googlefonts/googlesans-flex", "")
    offline = offline.replace("https://openfontlicense.org", "")
    assert "https://" not in offline
    assert "<script src" not in html
    assert "HTML projects supplied artifacts only" in html
    assert "Repository" in html
    assert "Committed files in assessment scope" in html
    assert "Assessed files" in html
    assert "not assessed coverage" in html
    assert "AnalysisResult identities" in html
    assert "Files observed" not in html
    assert 'id="trend"' in html
    assert 'id="actions"' in html
    assert 'id="modernization"' in html
    assert 'id="concentration"' in html
    assert 'id="hotspots"' in html
    assert "Business context was not supplied" in html
    assert "commerce-service" not in html
    assert (series / TREND_HTML_FILENAME).read_text(encoding="utf-8") == html
    from codestrata.application.incremental.trend_bundle import (
        create_trend_bundle,
        repository_trend_id,
    )

    bundle = create_trend_bundle(
        series,
        repository_id=repository_trend_id(tmp_path / "repo"),
        series_id=series.name,
    )
    assert render_trend_html(bundle) == html


def test_failed_slot_is_visually_distinct_from_available(tmp_path: Path) -> None:
    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
        assess=_fake_assess_factory([], fail_slot_sha=shas[2]),
    )
    html = (series / TREND_HTML_FILENAME).read_text(encoding="utf-8")
    assert "slot-status-failed" in html
    assert "slot-status-available" in html
    assert "comparison-unavailable" in html
    assert "s2-s3" in html
    assert "s3-s4" in html
    assert "This is not a clean or no-issue result." in html
    assert "Movement, lifecycle, deltas, and blast radius are unavailable" in html
    assert "not a runtime impact" in html or "UNKNOWN. M29" in html


def test_real_assess_html_matches_canonical_comparison_json(tmp_path: Path) -> None:
    repo, _shas = _five_commit_adversarial(tmp_path / "repo")
    series = tmp_path / "series"
    run_trend_series(
        repo,
        series,
        evaluation_time=PINNED,
        settings=_settings(tmp_path, repo),
    )
    html = (series / TREND_HTML_FILENAME).read_text(encoding="utf-8")
    s12 = (series / "comparisons" / "s1-s2" / "comparison.json").read_text(encoding="utf-8")
    s45 = (series / "comparisons" / "s4-s5" / "comparison.json").read_text(encoding="utf-8")
    assert "src/app.js" in html
    assert LATER_PATH in html
    assert LATER_PATH in s45
    assert LATER_PATH not in s12
    assert html.index("S1 → S2 · adjacent") < html.index("S1 → S5 · oldest to HEAD")
    for title in HEADLINE_TITLES:
        assert html.count(title.replace("&", "&amp;")) >= 2
    assert "Download trend-index.json" in html
    assert "Static bounded reach only" in html


def test_headline_titles_match_baseline_engineering_health() -> None:
    assert engineering_health_outcome_title("architecture_intelligence") == "Architecture"
    assert engineering_health_outcome_title("security_intelligence") == "Security"
    assert engineering_health_outcome_title("quality_intelligence") == "Quality"
    assert (
        engineering_health_outcome_title("technical_debt_intelligence")
        == "Maintainability & Technical Debt"
    )
