"""R01 publisher inventory helpers for publication preflight (E14.4)."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.application.release.publication.models import R01PreflightRecord


@dataclass(frozen=True, slots=True)
class WorkflowPublisherView:
    path: str
    name: str
    pypi_oidc_publish: bool
    engine_only_publish: bool
    aws_oidc: bool
    id_token_write: bool


def monorepo_ci_relabeled_as_publisher(workflows: tuple[WorkflowPublisherView, ...]) -> bool:
    """True when validation-only ci.yml is incorrectly treated as an OIDC publisher."""

    for item in workflows:
        normalized = item.path.replace("\\", "/")
        if not normalized.endswith(".github/workflows/ci.yml"):
            continue
        return item.pypi_oidc_publish or item.engine_only_publish
    return False


def build_r01_preflight_record(
    *,
    status: str,
    reason: str,
    engine_only_oidc_publisher: str | None,
    required_outside_engine_change: str,
    workflows: tuple[WorkflowPublisherView, ...],
) -> R01PreflightRecord:
    relabeled = monorepo_ci_relabeled_as_publisher(workflows)
    normalized_status = status if status in {"BLOCKED", "PRESENT"} else "BLOCKED"
    return R01PreflightRecord(
        status=normalized_status,  # type: ignore[arg-type]
        reason=reason,
        engine_only_oidc_publisher=engine_only_oidc_publisher,
        required_outside_engine_change=required_outside_engine_change,
        monorepo_ci_relabeled_as_publisher=relabeled,
        publication_performed=False,
    )
