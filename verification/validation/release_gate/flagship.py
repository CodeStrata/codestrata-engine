"""M15 confusion matrices for release-gate review (E06.3 / E15.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from verification.validation.release_gate.models import ConfusionMatrixRow

if TYPE_CHECKING:
    from codestrata.application.evidence.security.classification import ClassificationReport


def confusion_rows_from_report(report: ClassificationReport) -> tuple[ConfusionMatrixRow, ...]:
    rows: list[ConfusionMatrixRow] = []
    for group in report.groups:
        rows.append(
            ConfusionMatrixRow(
                group=group.group,
                true_positive=group.tp,
                false_positive=group.fp,
                false_negative=group.fn,
                true_negative=group.tn,
                unknown=group.unknown,
                unexplained_unknown=group.unexplained_unknown,
                precision=group.precision,
                recall=group.recall,
                promotion_blocked=report.promotion_blocked,
            )
        )
    return tuple(rows)
