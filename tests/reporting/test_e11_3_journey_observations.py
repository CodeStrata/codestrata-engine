"""Pinned repository observations. Expected numbers are fixture literals."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from codestrata.application.assessment.canonical_records import (
    seal_assess_canonical_records,
)
from codestrata.models.analysis_result import AnalysisResult
from codestrata.models.repository import Repository
from codestrata.reporting.assessment_canonical import (
    canonical_html_for_analysis,
    canonical_report_from_analysis,
)
from codestrata.reporting.canonical_views import project_canonical_json
from codestrata.reporting.journey_observations import (
    JOURNEY_EVALUATION_TIME,
    observe_repository,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "journeys"
_VIEWS = (
    "engineering-hotspots",
    "ownership-concentration",
    "temporal-co-change",
    "change-summary",
    "capability-coverage",
    "before-after-delta",
)


def _copy(name: str, destination: Path) -> Path:
    target = destination / name
    shutil.copytree(_EXAMPLES / name, target)
    return target


def _commit(repo: Path, *, name: str, email: str) -> None:
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        }
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            f"user.name={name}",
            "-c",
            f"user.email={email}",
            "commit",
            "-m",
            "pin fixture",
        ],
        check=True,
        capture_output=True,
        env=env,
    )


def _observe(repo: Path):
    return observe_repository(repo, evaluation_time=JOURNEY_EVALUATION_TIME)


def _analysis(repo: Path) -> AnalysisResult:
    return seal_assess_canonical_records(
        AnalysisResult(repository=Repository(name=repo.name, path=repo, files=["src/app.js"])),
        repository_root=repo,
        evaluation_time=JOURNEY_EVALUATION_TIME,
    )


def _html(repo: Path) -> str:
    return canonical_html_for_analysis(_analysis(repo))


def test_complete_fixture_ranks_one_hotspot_and_says_no_baseline(tmp_path: Path) -> None:
    repo = _copy("complete-js", tmp_path)
    _commit(repo, name="Ada Lovelace", email="ada@example.com")
    observed = _observe(repo)
    html = _html(repo)
    payload = project_canonical_json(canonical_report_from_analysis(_analysis(repo)))
    assert observed.hotspots[0].ranking_value == "12"
    assert observed.hotspots[0].subject_id == "src/app.js"
    assert observed.ownership[0].serialized_ratio == "1.000000"
    assert observed.ownership[0].status.value == "pass"
    assert observed.change_summary is not None
    assert observed.change_summary.affected_test_count == 1
    assert observed.change_summary.cutoff_reason is None
    assert observed.change_summary.boundary_spread_count is None
    assert "feed_fresh" in observed.limitations
    for view in _VIEWS:
        assert f'id="{view}"' in html
    assert "no baseline" in html
    assert "trend" not in html.lower()
    assert "healthy" not in html.lower()
    assert "health_score: none" in html
    assert "<script" not in html.lower()
    assert payload["health_score"] is None
    assert payload["hotspots"][0]["ranking_value"] == "12"
    assert "ranking_value: 12" in html
    assert "Stable" not in html
    assert 'href="#evidence-m16.function"' in html
    assert 'id="evidence-m16.function"' in html


def test_missing_git_and_feed_stay_unknown(tmp_path: Path) -> None:
    repo = tmp_path / "missing"
    (repo / "src").mkdir(parents=True)
    shutil.copy(_EXAMPLES / "complete-js" / "src" / "app.js", repo / "src" / "app.js")
    observed = _observe(repo)
    html = _html(repo)
    assert all(item.ranking_value is None for item in observed.hotspots)
    assert observed.ownership[0].serialized_ratio is None
    assert observed.ownership[0].status.value == "unknown"
    assert "missing_git_history" in html
    assert "feed_missing" in html
    assert "missing_test_association" in html
    assert "no baseline" in html
    assert "affected_test_count: 0" not in html
    assert "boundary_spread_count: 0" not in html
    assert "Stable" not in html
    assert "trend" not in html.lower()


def test_stale_feed_shallow_history_and_unknown_owner(tmp_path: Path) -> None:
    repo = _copy("stale-feed", tmp_path)
    _commit(repo, name="unknown", email="unknown@example.com")
    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    (repo / ".git" / "shallow").write_text(head + "\n", encoding="utf-8")
    observed = _observe(repo)
    html = _html(repo)
    assert any(item.ranking_value is None for item in observed.hotspots)
    assert observed.ownership[0].notes == "shallow_git_history"
    assert observed.ownership[0].serialized_ratio is None
    assert "feed_stale" in html
    assert "shallow_git_history" in html
    assert "unknown_ownership_mapping" not in html
    assert "0.000000" not in html
    summary = observed.change_summary
    assert summary is not None
    assert summary.affected_test_count is None
    assert summary.lower_bound is True
    assert "affected_test_count: UNKNOWN" in html


def test_unknown_owner_on_complete_history(tmp_path: Path) -> None:
    repo = _copy("stale-feed", tmp_path)
    _commit(repo, name="unknown", email="unknown@example.com")
    observed = _observe(repo)
    html = _html(repo)
    assert observed.ownership[0].notes == "unknown_ownership_mapping"
    assert observed.ownership[0].numerator is None
    assert "unknown_ownership_mapping" in html
    assert "feed_stale" in html


def test_impact_cutoff_and_cochange_pair(tmp_path: Path) -> None:
    repo = _copy("cutoff-js", tmp_path)
    _commit(repo, name="Ada Lovelace", email="ada@example.com")
    observed = _observe(repo)
    html = _html(repo)
    summary = observed.change_summary
    assert summary is not None
    assert summary.changed_file_count == 2
    assert summary.cutoff_reason == "impact_node_budget"
    assert summary.boundary_spread_count is None
    assert summary.crossed_boundary_count is None
    assert summary.affected_component_count is None
    assert summary.affected_test_count is None
    assert summary.visited_nodes == 1
    assert observed.cochange[0]["support"] == 1
    assert observed.cochange[0]["union"] == 1
    assert observed.cochange[0]["jaccard"] == "1.000000"
    assert "impact_node_budget" in html
    assert "missing_test_association" in html
    assert "affected_test_count: UNKNOWN" in html
    assert "boundary_spread_count: 0" not in html


def test_nested_directory_reads_only_its_own_history(tmp_path: Path) -> None:
    """A directory inside a larger checkout must not inherit the outer history.

    Regression: ``git log`` without a pathspec returned every commit of the
    enclosing repository, and the pairwise co-change loop then ran over
    thousands of unrelated files (hang plus multi-GB memory growth).
    """

    outer = tmp_path / "outer"
    outer.mkdir()
    subprocess.run(["git", "-C", str(outer), "init"], check=True, capture_output=True)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Ada Lovelace",
            "GIT_AUTHOR_EMAIL": "ada@example.com",
            "GIT_COMMITTER_NAME": "Ada Lovelace",
            "GIT_COMMITTER_EMAIL": "ada@example.com",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        }
    )

    def commit(message: str) -> None:
        subprocess.run(["git", "-C", str(outer), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(outer), "commit", "-q", "-m", message],
            check=True,
            capture_output=True,
            env=env,
        )

    # Unrelated outer history: three commits over six production files.
    for round_index in range(3):
        for file_index in range(6):
            path = outer / "unrelated" / "src" / f"module{file_index}.js"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"export const v{round_index} = {file_index};\n", encoding="utf-8")
        commit(f"outer {round_index}")
    # The observed directory is a nested fixture with one production file.
    inner = outer / "nested" / "fixture"
    shutil.copytree(_EXAMPLES / "complete-js", inner)
    commit("nested fixture")

    observed = _observe(inner)

    assert observed.change_summary is not None
    assert observed.change_summary.changed_file_ids == ("src/app.js",)
    assert observed.change_summary.changed_file_count == 1
    assert all(not item.subject_id.startswith("unrelated/") for item in observed.hotspots)
    assert observed.hotspots[0].subject_id == "src/app.js"
    assert observed.hotspots[0].ranking_value == "12"
    assert observed.ownership[0].serialized_ratio == "1.000000"
    assert observed.cochange[0]["unavailable_reason"] == "single_file_window"
    assert observed.cochange[0]["left"] == "src/app.js"
    assert "cochange_file_budget" not in observed.limitations


def test_cochange_pairs_are_bounded_and_use_support_threshold(monkeypatch) -> None:
    from codestrata.reporting import journey_observations as module

    commits = [
        {"src/a.js", "src/b.js", "src/c.js"},
        {"src/a.js", "src/b.js"},
        {"src/a.js", "src/b.js", "src/d.js"},
        {"src/e.js", "src/f.js"},
        {"src/g.js"},
    ]
    rows, truncated = module._cochange("complete", commits)
    assert truncated is False
    by_pair = {(row["left"], row["right"]): row for row in rows}
    # Only pairs that actually co-changed are emitted; no synthetic zero rows.
    assert all(row["support"] >= 1 for row in rows)
    assert ("src/a.js", "src/g.js") not in by_pair
    ab = by_pair[("src/a.js", "src/b.js")]
    assert ab["support"] == 3
    assert ab["union"] == 3
    assert ab["jaccard"] == "1.000000"
    assert ab["supported_relation"] is True
    ac = by_pair[("src/a.js", "src/c.js")]
    assert ac["support"] == 1
    assert ac["union"] == 3
    assert ac["jaccard"] == "0.333333"
    assert ac["supported_relation"] is False

    monkeypatch.setattr(module, "COCHANGE_FILE_BUDGET", 2)
    rows, truncated = module._cochange("complete", commits)
    assert truncated is True
    # The two most-changed files (a, b) are kept; the pair count is bounded.
    assert [(row["left"], row["right"]) for row in rows] == [("src/a.js", "src/b.js")]
    limitations = module._limitations(
        "complete",
        module._FeedView(
            reason="feed_fresh",
            state="fresh",
            provider="osv",
            digest="d",
            published_at=None,
            family_error=None,
            match_count=0,
            matching_reason="no_match",
            cannot_prove_clean=False,
        ),
        module._TestView(missing=False, count=1, test_ids=("t",)),
        None,
        truncated,
    )
    assert "cochange_file_budget" in limitations


def test_parse_log_strips_nested_prefix_and_ignores_outer_paths() -> None:
    from codestrata.reporting.journey_observations import _parse_log

    text = "\n".join(
        [
            "COMMIT\tabc\tAda\tada@example.com",
            "3\t1\tnested/fixture/src/app.js",
            "5\t0\tunrelated/src/module0.js",
            "COMMIT\tdef\tAda\tada@example.com",
            "2\t2\tnested/fixture/src/other.js",
        ]
    )
    churn, authors, unknown, commits = _parse_log(text, prefix="nested/fixture/")
    assert churn == {"src/app.js": 4, "src/other.js": 4}
    assert authors == {"Ada <ada@example.com>": 8}
    assert unknown is False
    assert commits == [{"src/app.js"}, {"src/other.js"}]


def test_corrupt_feed_keeps_the_failed_family(tmp_path: Path) -> None:
    repo = _copy("complete-js", tmp_path)
    snapshot = repo / "codestrata" / "osv-snapshot.json"
    snapshot.write_text("{", encoding="utf-8")
    _commit(repo, name="Ada Lovelace", email="ada@example.com")
    observed = _observe(repo)
    html = _html(repo)
    assert "feed_unreadable" in observed.limitations
    assert "failed_family_vulnerability" in observed.limitations
    assert "feed_unreadable" in html
    assert 'id="engineering-hotspots"' in html
    assert "healthy" not in html.lower()


def test_sealed_records_do_not_reobserve_live_head(tmp_path: Path, monkeypatch) -> None:
    repo = _copy("complete-js", tmp_path)
    _commit(repo, name="Ada Lovelace", email="ada@example.com")
    sealed = _analysis(repo)

    def _forbidden(root, **_: object):
        raise AssertionError(f"live HEAD re-observed at {root}")

    monkeypatch.setattr(
        "codestrata.reporting.assessment_canonical.observe_repository",
        _forbidden,
    )
    monkeypatch.setattr(
        "codestrata.reporting.journey_observations.observe_repository",
        _forbidden,
    )
    report = canonical_report_from_analysis(sealed)
    assert report.envelope.body.hotspots
    assert report.envelope.body.ownership
    assert sealed.metadata["dirty"] is False
    assert sealed.repository.metadata["source_revision"] != "unavailable"


def test_p10_complete_and_cutoff_keep_four_outcomes_without_score(tmp_path: Path) -> None:
    for name in ("complete-js", "cutoff-js", "stale-feed"):
        repo = _copy(name, tmp_path)
        _commit(repo, name="Ada Lovelace", email="ada@example.com")
        payload = project_canonical_json(canonical_report_from_analysis(_analysis(repo)))
        assert payload["health_score"] is None
        html = _html(repo)
        assert "health_score: none" in html
        assert "Five-commit health trend" not in html
        assert "no baseline" in html


def test_secret_text_is_redacted_in_each_projection() -> None:
    from codestrata.domain.contracts.examples import example_complete
    from codestrata.reporting.canonical_views import (
        CanonicalReportInput,
        project_canonical_html,
        project_canonical_json,
        project_canonical_sarif,
    )
    from codestrata.security.redaction import redact_report_payload, redact_secrets

    secret = "AKIA1234567890ABCDEF"
    report = CanonicalReportInput(envelope=example_complete())
    assert secret not in project_canonical_html(report)
    assert secret not in str(project_canonical_json(report))
    assert secret not in str(project_canonical_sarif(report))
    analysis = redact_report_payload({"findings": [{"description": f"literal {secret}"}]})
    assert secret not in str(analysis)
    assert "[REDACTED]" in redact_secrets(f"literal {secret}")
