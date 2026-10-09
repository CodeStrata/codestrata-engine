"""Orchestrate M12 resolution coverage and M13 OSV matching."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from codestrata.application.evidence.supply_chain.collect import (
    attach_lock_paths,
    collect_supply_chain_inputs,
)
from codestrata.application.evidence.supply_chain.coverage import (
    compute_scope_coverage,
    count_hygiene,
)
from codestrata.application.evidence.supply_chain.envelope import (
    SupplyChainEnvelope,
    SupplyChainOperationalMetadata,
    seal_supply_chain_envelope,
)
from codestrata.application.evidence.supply_chain.feed import (
    evaluate_freshness,
    load_osv_snapshot,
    load_osv_snapshot_payload,
)
from codestrata.application.evidence.supply_chain.licenses import collect_license_records
from codestrata.application.evidence.supply_chain.match import match_vulnerabilities
from codestrata.application.evidence.supply_chain.models import (
    LicensePolicy,
    MatchingStatus,
    SupplyChainEvidence,
)


class SupplyChainEvidenceService:
    """Collect lock resolution and match a pinned OSV snapshot. No network."""

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        evaluation_time: datetime,
        snapshot_path: Path | None = None,
        snapshot_payload: dict[str, Any] | None = None,
        yaml_default_severity: str = "high",
        catalog_digest: str = "",
        assessed_git_repo: str | None = None,
        operational: SupplyChainOperationalMetadata | None = None,
        license_policy: LicensePolicy | None = None,
        license_overlay: Sequence[Any] | None = None,
    ) -> tuple[SupplyChainEvidence, SupplyChainEnvelope]:
        declarations, occurrences, diagnostics = collect_supply_chain_inputs(
            relative_paths=relative_paths,
            file_texts=file_texts,
        )
        declarations = attach_lock_paths(declarations, occurrences)
        unknown_ecosystem = any(item.startswith("unknown_ecosystem:") for item in diagnostics)
        unparsed_lock = any(item.startswith("lock_format_unparsed:") for item in diagnostics)
        scopes = compute_scope_coverage(
            declarations,
            occurrences,
            unknown_ecosystem=unknown_ecosystem and not declarations,
        )
        if unparsed_lock and not any(item.denominator for item in scopes):
            scopes = compute_scope_coverage((), (), unknown_ecosystem=True)
        snapshot = (
            load_osv_snapshot_payload(snapshot_payload)
            if snapshot_payload is not None
            else load_osv_snapshot(snapshot_path)
        )
        freshness = evaluate_freshness(snapshot, evaluation_time=evaluation_time)
        matches, matching, unknown_versions = match_vulnerabilities(
            occurrences,
            snapshot,
            freshness,
            yaml_default_severity=yaml_default_severity,
            assessed_git_repo=assessed_git_repo,
        )
        licenses, license_summary = collect_license_records(
            relative_paths=relative_paths,
            file_texts=file_texts,
            policy=license_policy,
            overlay=tuple(license_overlay or ()),
        )
        limitations = list(diagnostics)
        if matching.status is not MatchingStatus.COMPLETE:
            limitations.append(f"matching_{matching.reason}")
        if unknown_versions:
            limitations.append("unsupported_version_scheme")
        if license_policy is None or not license_policy.present:
            limitations.append("license_policy_absent_metadata_only")
        if license_summary.unknown:
            limitations.append("license_unknown_not_guessed")
        limitations.append("license_not_legal_compliance")
        evidence = SupplyChainEvidence(
            repository_id=repository_id,
            declarations=declarations,
            occurrences=occurrences,
            scopes=scopes,
            hygiene=count_hygiene(declarations),
            freshness=freshness,
            matching=matching,
            matches=matches,
            licenses=licenses,
            license_policy=license_policy,
            license_summary=license_summary,
            unknown_version_packages=unknown_versions,
            limitations=tuple(sorted(set(limitations))),
        )
        envelope = seal_supply_chain_envelope(
            evidence=evidence,
            catalog_digest=catalog_digest,
            operational=operational,
        )
        return evidence, envelope
