"""Deterministic bounded outlier analysis (informational unless contract violation)."""

from __future__ import annotations

from collections import Counter

from verification.assessment_consistency.models import OutlierRecord, RepositoryBundle


def build_outliers(bundles: list[RepositoryBundle]) -> list[OutlierRecord]:
    outliers: list[OutlierRecord] = []
    finding_counts = {b.repository_id: len(b.findings) for b in bundles}
    rec_counts = {b.repository_id: len(b.recommendations) for b in bundles}
    pa_counts = {
        b.repository_id: len(b.assessment.get("priority_actions") or []) for b in bundles
    }
    tech_counts = {
        b.repository_id: len(b.assessment.get("technologies") or []) for b in bundles
    }

    # Unique activation/coverage states not seen elsewhere are informational.
    cov_status_by_repo: dict[str, Counter[str]] = {}
    for bundle in bundles:
        counter: Counter[str] = Counter()
        cov = bundle.assessment.get("assessment_coverage") or {}
        if isinstance(cov, dict):
            for entry in cov.values():
                if isinstance(entry, dict):
                    counter[str(entry.get("status"))] += 1
        cov_status_by_repo[bundle.repository_id] = counter
        unavailable = counter.get("unavailable", 0)
        if unavailable:
            outliers.append(
                OutlierRecord(
                    repository_id=bundle.repository_id,
                    metric="unavailable_coverage_count",
                    observed_value=unavailable,
                    comparison_scope="coverage_heads",
                    expected_contract="unavailable remains a first-class coverage state",
                    contract_violation=False,
                    explanation="informational",
                )
            )

    # Max finding count — informational, never "bad".
    if finding_counts:
        max_rid = max(finding_counts, key=finding_counts.get)
        outliers.append(
            OutlierRecord(
                repository_id=max_rid,
                metric="finding_count_max",
                observed_value=finding_counts[max_rid],
                comparison_scope="all_repositories",
                expected_contract="Finding counts may differ by repository facts",
                contract_violation=False,
                explanation="many Findings is not classified as a defect",
            )
        )
        min_rid = min(finding_counts, key=finding_counts.get)
        outliers.append(
            OutlierRecord(
                repository_id=min_rid,
                metric="finding_count_min",
                observed_value=finding_counts[min_rid],
                comparison_scope="all_repositories",
                expected_contract="zero/low Finding counts are not health scores",
                contract_violation=False,
                explanation="low Finding count is not higher quality",
            )
        )

    for rid, count in rec_counts.items():
        if count == 0:
            outliers.append(
                OutlierRecord(
                    repository_id=rid,
                    metric="recommendation_count_zero",
                    observed_value=0,
                    comparison_scope="recommendations",
                    expected_contract="zero Recommendations allowed when evidence warrants",
                    contract_violation=False,
                )
            )

    for rid, count in pa_counts.items():
        outliers.append(
            OutlierRecord(
                repository_id=rid,
                metric="priority_action_count",
                observed_value=count,
                comparison_scope="priority_actions",
                expected_contract="PA counts vary by recommendation authority",
                contract_violation=False,
            )
        )

    for rid, count in tech_counts.items():
        outliers.append(
            OutlierRecord(
                repository_id=rid,
                metric="technology_count",
                observed_value=count,
                comparison_scope="technologies",
                expected_contract="inventory counts vary by repository",
                contract_violation=False,
            )
        )

    # Duration buckets from records
    for bundle in bundles:
        bucket = bundle.record.get("duration_bucket")
        if bucket == "over_10m":
            outliers.append(
                OutlierRecord(
                    repository_id=bundle.repository_id,
                    metric="runtime_bucket",
                    observed_value=bucket,
                    comparison_scope="sv10_records",
                    expected_contract="slow repositories remain valid when completed",
                    contract_violation=False,
                    explanation="BookStack/Known Issues may be slow; not a consistency defect",
                )
            )

    # Stable sort
    outliers.sort(key=lambda o: (o.repository_id, o.metric, str(o.observed_value)))
    return outliers
