"""M31 Cause Attribution across Source, Feed, and Configuration Dimensions.

Standing rules:
- Attributions: source_only, feed_only, configuration_only, coverage_only, mixed,
  or undetermined.
- Same-code feed changes must be labeled feed-driven.
- Feed-driven CVE changes cannot be called customer code deterioration.
- If multiple dimensions differ, only controlled equivalent-input comparisons justify
  isolated cause.
- No AI-causality inference.
- Lack of controlled evidence => mixed/undetermined, never guessing dominant cause.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.models.scan_comparison import (
    CauseAttribution,
    ComparedFinding,
    ControlledRerunReference,
)


def evaluate_cause_attribution(
    *,
    source_changed: bool = False,
    feed_changed: bool = False,
    config_changed: bool = False,
    coverage_changed: bool = False,
    engine_changed: bool = False,
    controlled_rerun: bool = False,
    controlled_reruns: Sequence[ControlledRerunReference] = (),
    base_digests: Mapping[str, str | None] | None = None,
    candidate_digests: Mapping[str, str | None] | None = None,
    cve_findings: Sequence[ComparedFinding] = (),
    finding_causes: Mapping[str, str] | None = None,
    isolated_causes: Mapping[str, Sequence[str]] | None = None,
) -> CauseAttribution:
    """Determine cause attribution for observed finding/metric movement."""
    # Auto-detect changed dimensions from digests if provided
    base_d: dict[str, str | None] = dict(base_digests) if base_digests else {}
    cand_d: dict[str, str | None] = dict(candidate_digests) if candidate_digests else {}

    if base_d and cand_d:
        for dim, key in [
            ("source", "source"),
            ("feed", "feed"),
            ("config", "config"),
            ("coverage", "coverage"),
            ("engine", "engine"),
        ]:
            b_val = base_d.get(key)
            c_val = cand_d.get(key)
            if b_val is not None and c_val is not None and b_val != c_val:
                if dim == "source":
                    source_changed = True
                elif dim == "feed":
                    feed_changed = True
                elif dim == "config":
                    config_changed = True
                elif dim == "coverage":
                    coverage_changed = True
                elif dim == "engine":
                    engine_changed = True

    changed_dims: list[str] = []
    if source_changed:
        changed_dims.append("source")
    if feed_changed:
        changed_dims.append("feed")
    if config_changed:
        changed_dims.append("configuration")
    if coverage_changed:
        changed_dims.append("coverage")
    if engine_changed:
        changed_dims.append("engine")

    notes: list[str] = []
    controlled_reruns_list = list(controlled_reruns)
    rerun_refs = [r.rerun_id for r in controlled_reruns_list]
    iso_map: dict[str, list[str]] = (
        {k: list(v) for k, v in isolated_causes.items()} if isolated_causes else {}
    )

    if not changed_dims:
        return CauseAttribution(
            attribution="undetermined",
            label="undetermined",
            changed_dimensions=[],
            controlled_rerun_performed=controlled_rerun or bool(controlled_reruns_list),
            controlled_reruns=controlled_reruns_list,
            controlled_rerun_references=rerun_refs,
            isolated_causes=iso_map,
            base_digests=base_d,
            candidate_digests=cand_d,
            customer_code_deterioration=False,
            is_feed_driven=False,
            evidence_notes=["no_dimension_changes_observed"],
        )

    if len(changed_dims) == 1:
        dim = changed_dims[0]
        attr = f"{dim}_only"
        is_feed = dim == "feed"
        label = "feed-driven" if is_feed else f"{dim}-driven"

        if is_feed:
            notes.append("feed_driven_cve_changes_not_customer_code_deterioration")
            cust_deterioration = False
        elif dim == "configuration":
            notes.append("policy_override_or_config_change_not_source_fix")
            cust_deterioration = False
        elif dim == "coverage":
            notes.append("coverage_change_forces_unknown_lifecycle")
            cust_deterioration = False
        else:
            cust_deterioration = any(
                f.lifecycle in ("new", "worsened") for f in cve_findings
            )

        return CauseAttribution(
            attribution=attr,
            label=label,
            changed_dimensions=changed_dims,
            controlled_rerun_performed=controlled_rerun or bool(controlled_reruns_list),
            controlled_reruns=controlled_reruns_list,
            controlled_rerun_references=rerun_refs,
            isolated_causes=iso_map,
            base_digests=base_d,
            candidate_digests=cand_d,
            customer_code_deterioration=cust_deterioration,
            is_feed_driven=is_feed,
            evidence_notes=notes,
        )

    # Multiple dimensions differ. A boolean flag is not a controlled rerun record.
    if controlled_reruns_list:
        notes.append("controlled_rerun_validated")
        for r in controlled_reruns_list:
            if r.isolated_dimension and r.isolated_finding_keys:
                existing = iso_map.get(r.isolated_dimension, [])
                iso_map.setdefault(r.isolated_dimension, []).extend(
                    k for k in r.isolated_finding_keys if k not in existing
                )

        has_source_deterioration = any(
            f.lifecycle in ("new", "worsened")
            and f.identity_key in iso_map.get("source", [])
            for f in cve_findings
        )
        return CauseAttribution(
            attribution="controlled_isolated",
            label="controlled-isolated",
            changed_dimensions=changed_dims,
            controlled_rerun_performed=True,
            controlled_reruns=controlled_reruns_list,
            controlled_rerun_references=rerun_refs,
            isolated_causes=iso_map,
            base_digests=base_d,
            candidate_digests=cand_d,
            customer_code_deterioration=has_source_deterioration,
            is_feed_driven=bool(iso_map.get("feed")) and not bool(iso_map.get("source")),
            evidence_notes=notes,
        )

    # Without controlled rerun, NEVER guess dominant cause!
    notes.append("multiple_dimensions_differ_without_controlled_rerun")
    return CauseAttribution(
        attribution="mixed",
        label="mixed",
        changed_dimensions=changed_dims,
        controlled_rerun_performed=False,
        controlled_reruns=[],
        controlled_rerun_references=[],
        isolated_causes={},
        base_digests=base_d,
        candidate_digests=cand_d,
        customer_code_deterioration=False,
        is_feed_driven=False,
        evidence_notes=notes,
    )


def isolate_causes_with_controlled_reruns(
    *,
    base_finding_keys: Sequence[str],
    candidate_finding_keys: Sequence[str],
    source_rerun_finding_keys: Sequence[str] | None = None,  # Candidate source + base feed
    feed_rerun_finding_keys: Sequence[str] | None = None,    # Base source + candidate feed
    base_digests: Mapping[str, str | None] | None = None,
    candidate_digests: Mapping[str, str | None] | None = None,
) -> CauseAttribution:
    """Isolate source vs feed causes by comparing controlled equivalent-input reruns."""
    base_set = set(base_finding_keys)

    controlled_reruns: list[ControlledRerunReference] = []
    isolated_causes: dict[str, list[str]] = {"source": [], "feed": []}

    # If source rerun provided (candidate source + base feed)
    if source_rerun_finding_keys is not None:
        src_set = set(source_rerun_finding_keys)
        # Findings introduced or resolved by candidate source alone
        src_diff = sorted((src_set - base_set) | (base_set - src_set))
        isolated_causes["source"] = src_diff
        controlled_reruns.append(
            ControlledRerunReference(
                rerun_id="controlled_rerun_candidate_source_base_feed",
                isolated_dimension="source",
                isolated_finding_keys=src_diff,
                notes=["isolated_source_changes_against_base_feed"],
            )
        )

    # If feed rerun provided (base source + candidate feed)
    if feed_rerun_finding_keys is not None:
        feed_set = set(feed_rerun_finding_keys)
        # Findings introduced or resolved by candidate feed alone
        feed_diff = sorted((feed_set - base_set) | (base_set - feed_set))
        isolated_causes["feed"] = feed_diff
        controlled_reruns.append(
            ControlledRerunReference(
                rerun_id="controlled_rerun_base_source_candidate_feed",
                isolated_dimension="feed",
                isolated_finding_keys=feed_diff,
                notes=["isolated_feed_changes_against_base_source"],
            )
        )

    # Findings in candidate that are in feed_diff are feed-driven
    # Findings in candidate that are in src_diff are source-driven
    return evaluate_cause_attribution(
        source_changed=True,
        feed_changed=True,
        controlled_rerun=True,
        controlled_reruns=controlled_reruns,
        base_digests=base_digests,
        candidate_digests=candidate_digests,
        isolated_causes=isolated_causes,
    )
