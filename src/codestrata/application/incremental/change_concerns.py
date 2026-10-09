"""M29 Named Contextual Change Concern Join.

Joins changed subjects to configured comparable base/candidate churn and centrality measures.
Freezes exact E01.1 high-churn/high-centrality predicates and deterministic ranking.

Standing rules:
- Context-only default role. Verdict-driving requires explicit YAML semantics.
- Exact predicates:
  - high_churn: changed_lines > 0 and changed_lines > nearest-rank p90 among >0 churn
    in pinned M24 window.
  - high_centrality: M09 centrality(v) > nearest-rank p90 of the comparable universe V.
- Lexicographic ranking: both > churn-only > centrality-only > ordinary; then more changed lines;
  then higher centrality; then subject ID ascending.
- No weighted composite score or calibrated failure probability.
- Partial contributors remain visible when history or centrality data is incomplete.
- Deleted subjects use available base evidence.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal

from codestrata.domain.contracts.formulas import (
    m29_concern_class,
    m29_high_centrality,
    m29_high_churn,
    m29_rank_key,
    nearest_rank_percentile,
)
from codestrata.models.scan_comparison import ChangeConcern


def evaluate_change_concerns(
    changed_subjects: Sequence[str],
    *,
    churn_by_component: Mapping[str, int] | None = None,
    centrality_by_component: Mapping[str, Decimal | float] | None = None,
    comparable_universe: Sequence[str] = (),
    history_window: str | None = "180d_then_latest_1000",
    history_profile_id: str | None = "git.history.reachable-non-merge-180d-1000",
    deleted_subjects: Sequence[str] = (),
    base_churn_by_component: Mapping[str, int] | None = None,
    base_centrality_by_component: Mapping[str, Decimal | float] | None = None,
    has_history: bool = True,
    has_centrality: bool = True,
) -> list[ChangeConcern]:
    """Execute the versioned M29 change-concern join over changed subjects."""
    clean_subjects = list(dict.fromkeys(s for s in changed_subjects if s))
    deleted_set = set(deleted_subjects)

    churn_map = dict(churn_by_component or {})
    base_churn_map = dict(base_churn_by_component or {})
    centrality_map: dict[str, Decimal] = {}
    if centrality_by_component:
        for k, v in centrality_by_component.items():
            centrality_map[k] = Decimal(str(v))

    base_centrality_map: dict[str, Decimal] = {}
    if base_centrality_by_component:
        for k, v in base_centrality_by_component.items():
            base_centrality_map[k] = Decimal(str(v))

    # 1. Churn p90 calculation: components with >0 churn in the pinned window
    churn_positive = [c for c in churn_map.values() if c > 0]
    if churn_positive and has_history:
        p90_churn_calc = nearest_rank_percentile(churn_positive, 0.9)
        p90_churn = int(p90_churn_calc.value) if p90_churn_calc.value is not None else 0
    else:
        p90_churn = 0

    # 2. Centrality p90 calculation over comparable universe V
    universe_nodes = list(dict.fromkeys(comparable_universe or list(centrality_map.keys())))
    centrality_values = [
        centrality_map.get(u, Decimal("0"))
        for u in universe_nodes
    ]
    if centrality_values and has_centrality:
        ordered_cent = sorted(centrality_values)
        rank = max(1, math.ceil(0.9 * len(ordered_cent)))
        p90_centrality = ordered_cent[rank - 1]
    else:
        p90_centrality = Decimal("0")

    centrality_denom = max(1, len(universe_nodes) - 1)

    concerns: list[ChangeConcern] = []

    for subject in clean_subjects:
        is_deleted = subject in deleted_set

        # Use base evidence for deleted subjects
        if is_deleted:
            lines = base_churn_map.get(subject, churn_map.get(subject, 0))
            cent = base_centrality_map.get(subject, centrality_map.get(subject, Decimal("0")))
        else:
            lines = churn_map.get(subject, 0)
            cent = centrality_map.get(subject, Decimal("0"))

        reasons: list[str] = []
        witnesses: list[str] = [f"subject:{subject}"]
        partial = False

        if not has_history:
            partial = True
            reasons.append("missing_history_window")
            high_churn_flag = False
        else:
            high_churn_flag = m29_high_churn(lines, p90_churn)
            reasons.append(f"churn={lines}; p90={p90_churn}")

        if not has_centrality or not universe_nodes:
            partial = True
            reasons.append("missing_centrality_evidence")
            high_centrality_flag = False
        else:
            high_centrality_flag = m29_high_centrality(cent, p90_centrality)
            reasons.append(f"centrality={cent}; p90={p90_centrality}")

        concern_cls = m29_concern_class(
            high_churn=high_churn_flag,
            high_centrality=high_centrality_flag,
        )

        rank_key = list(
            m29_rank_key(
                subject,
                high_churn=high_churn_flag,
                high_centrality=high_centrality_flag,
                changed_lines=lines,
                centrality=cent,
            )
        )

        concerns.append(
            ChangeConcern(
                subject_id=subject,
                concern_class=concern_cls,
                role="context_only",
                changed_lines=lines,
                churn_p90=p90_churn,
                centrality=float(cent),
                centrality_p90=float(p90_centrality),
                centrality_denominator=centrality_denom,
                window=history_window,
                history_profile_id=history_profile_id,
                reasons=reasons,
                witnesses=witnesses,
                partial_contributors=partial,
                ranking_key=rank_key,
                deleted=is_deleted,
            )
        )

    # Sort deterministically by m29 rank key
    concerns.sort(key=lambda c: c.ranking_key)
    return concerns
