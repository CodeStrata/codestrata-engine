"""Deterministic OSV matching against resolved exact versions (M13)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from codestrata.application.evidence.supply_chain.feed import OsvSnapshot
from codestrata.application.evidence.supply_chain.models import (
    FeedFreshness,
    FreshnessStatus,
    MatchingScope,
    MatchingStatus,
    ResolutionOccurrence,
    VulnerabilityMatch,
)
from codestrata.application.evidence.supply_chain.versions import (
    VersionSchemeError,
    version_in_osv_range,
)
from codestrata.domain.evidence.language.identifiers import stable_evidence_id
from codestrata.domain.rules.enums import RuleSeverity

ECOSYSTEM_TO_OSV = {
    "python": "PyPI",
    "npm": "npm",
    "maven": "Maven",
    "gradle": "Maven",
    "nuget": "NuGet",
    "composer": "Packagist",
}

RANGE_SCHEMES = {"SEMVER": "SEMVER", "ECOSYSTEM": "ECOSYSTEM"}


def canonical_alias_groups(advisories: list[dict[str, Any]]) -> dict[str, str]:
    """Union-find over advisory IDs and aliases. Canonical ID is the sorted min."""

    parent: dict[str, str] = {}

    def ident(value: str) -> str:
        return value.strip()

    def find(key: str) -> str:
        parent.setdefault(key, key)
        if parent[key] != key:
            parent[key] = find(parent[key])
        return parent[key]

    def union(left: str, right: str) -> None:
        root_l, root_r = find(left), find(right)
        if root_l == root_r:
            return
        chosen = min(root_l, root_r)
        other = root_r if chosen == root_l else root_l
        parent[other] = chosen

    for advisory in advisories:
        advisory_id = ident(str(advisory.get("id") or ""))
        if not advisory_id:
            continue
        find(advisory_id)
        for alias in advisory.get("aliases") or []:
            alias_id = ident(str(alias))
            if alias_id:
                union(advisory_id, alias_id)
    return {key: find(key) for key in parent}


def feed_severity_of(advisory: dict[str, Any]) -> tuple[str, RuleSeverity | None]:
    """Return (visible token, mapped severity or None if unknown)."""

    database = advisory.get("database_specific")
    if isinstance(database, dict):
        raw = database.get("severity")
        if isinstance(raw, str) and raw.strip():
            mapped = _map_severity_token(raw)
            return raw.strip().lower(), mapped
    severities = advisory.get("severity")
    if isinstance(severities, list):
        for item in severities:
            if not isinstance(item, dict):
                continue
            score = str(item.get("score") or "")
            vector_severity = _cvss_from_vector(score)
            if vector_severity is not None:
                return vector_severity.value, vector_severity
            numeric = item.get("score")
            mapped = _map_cvss_number(numeric)
            if mapped is not None:
                return mapped.value, mapped
    return "unknown", None


def _map_severity_token(token: str) -> RuleSeverity | None:
    lowered = token.strip().lower()
    mapping = {
        "critical": RuleSeverity.CRITICAL,
        "high": RuleSeverity.HIGH,
        "medium": RuleSeverity.MEDIUM,
        "moderate": RuleSeverity.MEDIUM,
        "low": RuleSeverity.LOW,
        "informational": RuleSeverity.INFORMATIONAL,
        "info": RuleSeverity.INFORMATIONAL,
    }
    return mapping.get(lowered)


def _cvss_from_vector(score: str) -> RuleSeverity | None:
    token = _map_severity_token(score)
    if token is not None:
        return token
    return _map_cvss_number(score)


def _map_cvss_number(value: object) -> RuleSeverity | None:
    try:
        number = float(str(value).split("/")[0])
    except ValueError:
        return None
    if number >= 9.0:
        return RuleSeverity.CRITICAL
    if number >= 7.0:
        return RuleSeverity.HIGH
    if number >= 4.0:
        return RuleSeverity.MEDIUM
    if number > 0:
        return RuleSeverity.LOW
    return None


def match_vulnerabilities(
    occurrences: tuple[ResolutionOccurrence, ...],
    snapshot: OsvSnapshot | None,
    freshness: FeedFreshness,
    *,
    yaml_default_severity: str,
    assessed_git_repo: str | None = None,
) -> tuple[tuple[VulnerabilityMatch, ...], MatchingScope, tuple[str, ...]]:
    """Match exact resolved versions. Missing/stale feed cannot prove clean."""

    unknown_versions = tuple(
        sorted(
            {
                f"{item.ecosystem}:{item.package_name}"
                for item in occurrences
                if item.unsupported_scheme or not item.exact or not item.resolved_version
            }
        )
    )
    if snapshot is None:
        return (), _unknown_scope("feed_missing"), unknown_versions
    if freshness.status is FreshnessStatus.UNKNOWN:
        return (), _unknown_scope(freshness.reason), unknown_versions
    if freshness.status is FreshnessStatus.STALE:
        matches = _compute_matches(
            occurrences,
            snapshot,
            yaml_default_severity=yaml_default_severity,
            assessed_git_repo=assessed_git_repo,
            qualified=True,
            qualification_reason="feed_stale",
        )
        return (
            matches,
            MatchingScope(
                status=MatchingStatus.UNKNOWN,
                reason="feed_stale",
                match_count=len(matches) if matches else None,
                cannot_prove_clean=True,
            ),
            unknown_versions,
        )

    matches = _compute_matches(
        occurrences,
        snapshot,
        yaml_default_severity=yaml_default_severity,
        assessed_git_repo=assessed_git_repo,
        qualified=False,
        qualification_reason=None,
    )
    exact_ready = any(item.exact and item.resolved_version for item in occurrences)
    if not exact_ready:
        return (
            (),
            MatchingScope(
                status=MatchingStatus.UNKNOWN,
                reason="no_exact_version",
                match_count=None,
                cannot_prove_clean=True,
            ),
            unknown_versions,
        )
    return (
        matches,
        MatchingScope(
            status=MatchingStatus.COMPLETE,
            reason="fresh_supported_feed",
            match_count=len(matches),
            cannot_prove_clean=False,
            zero_is_not_secure=True,
        ),
        unknown_versions,
    )


def _unknown_scope(reason: str) -> MatchingScope:
    return MatchingScope(
        status=MatchingStatus.UNKNOWN,
        reason=reason,
        match_count=None,
        cannot_prove_clean=True,
    )


def _compute_matches(
    occurrences: tuple[ResolutionOccurrence, ...],
    snapshot: OsvSnapshot,
    *,
    yaml_default_severity: str,
    assessed_git_repo: str | None,
    qualified: bool,
    qualification_reason: str | None,
) -> tuple[VulnerabilityMatch, ...]:
    groups = canonical_alias_groups(snapshot.advisories)
    # Finding key: alias-group + ecosystem + package + version
    collected: dict[tuple[str, str, str, str], VulnerabilityMatch] = {}
    paths: dict[tuple[str, str, str, str], list[tuple[str, ...]]] = defaultdict(list)
    by_osv: dict[tuple[str, str], list[ResolutionOccurrence]] = defaultdict(list)
    for item in occurrences:
        if not item.exact or not item.resolved_version or item.unsupported_scheme:
            continue
        osv_eco = ECOSYSTEM_TO_OSV.get(item.ecosystem)
        if osv_eco is None:
            continue
        by_osv[(osv_eco, item.package_name.lower())].append(item)

    for advisory in snapshot.advisories:
        if advisory.get("withdrawn"):
            continue
        advisory_id = str(advisory.get("id") or "").strip()
        if not advisory_id:
            continue
        aliases = tuple(
            sorted(
                {str(item).strip() for item in (advisory.get("aliases") or []) if str(item).strip()}
            )
        )
        alias_group = groups.get(advisory_id, advisory_id)
        severity_token, mapped = feed_severity_of(advisory)
        if mapped is None:
            effective = yaml_default_severity
            basis = "yaml_catalog_default,feed_severity_unknown"
        else:
            effective = mapped.value
            basis = "osv_feed_deterministic"
        for affected in advisory.get("affected") or []:
            if not isinstance(affected, dict):
                continue
            package = affected.get("package") or {}
            if not isinstance(package, dict):
                continue
            ecosystem = str(package.get("ecosystem") or "")
            name = str(package.get("name") or "").strip().lower()
            if not ecosystem or not name:
                continue
            candidates = by_osv.get((ecosystem, name), ())
            if not candidates:
                continue
            listed = {str(item) for item in (affected.get("versions") or []) if str(item).strip()}
            ranges = [item for item in (affected.get("ranges") or []) if isinstance(item, dict)]
            for occurrence in candidates:
                version = occurrence.resolved_version or ""
                hit, range_text, scheme_ok = _version_is_affected(
                    version,
                    listed,
                    ranges,
                    assessed_git_repo=assessed_git_repo,
                    package_repo=str(package.get("purl") or package.get("repository") or ""),
                )
                if not scheme_ok:
                    continue
                if not hit:
                    continue
                key = (alias_group, ecosystem, name, version)
                paths[key].append(occurrence.dependency_path)
                if key in collected:
                    continue
                collected[key] = VulnerabilityMatch(
                    finding_id=stable_evidence_id(
                        "supply_chain.match",
                        alias_group,
                        ecosystem,
                        name,
                        version,
                    ),
                    alias_group=alias_group,
                    advisory_id=advisory_id,
                    aliases=aliases,
                    ecosystem=occurrence.ecosystem,
                    package_name=occurrence.package_name,
                    resolved_version=version,
                    affected_range=range_text,
                    feed_severity=severity_token,
                    yaml_default_severity=yaml_default_severity,
                    effective_severity=effective,
                    severity_basis=basis,
                    snapshot_digest=snapshot.digest,
                    published_at=snapshot.published_at or None,
                    lock_path=occurrence.lock_path,
                    dependency_paths=(),
                    withdrawn=False,
                    qualified=qualified,
                    qualification_reason=qualification_reason,
                )
    ordered: list[VulnerabilityMatch] = []
    for key, match in sorted(collected.items(), key=lambda item: item[0]):
        unique_paths = tuple(sorted(set(paths[key])))
        ordered.append(match.model_copy(update={"dependency_paths": unique_paths}))
    return tuple(ordered)


def _version_is_affected(
    version: str,
    listed: set[str],
    ranges: list[dict[str, Any]],
    *,
    assessed_git_repo: str | None,
    package_repo: str,
) -> tuple[bool, str, bool]:
    if version in listed:
        return True, f"versions:{version}", True
    descriptions: list[str] = []
    any_supported_range = False
    matched = False
    for item in ranges:
        range_type = str(item.get("type") or "").upper()
        events = [event for event in (item.get("events") or []) if isinstance(event, dict)]
        event_map = [
            {str(key): str(value) for key, value in event.items() if value is not None}
            for event in events
        ]
        if range_type == "GIT":
            repo = str(item.get("repo") or package_repo)
            if (
                not assessed_git_repo
                or not repo
                or repo.rstrip("/") != assessed_git_repo.rstrip("/")
            ):
                continue
            any_supported_range = True
            descriptions.append("GIT")
            continue
        scheme = RANGE_SCHEMES.get(range_type)
        if scheme is None:
            continue
        any_supported_range = True
        descriptions.append(f"{range_type}:{_event_text(event_map)}")
        try:
            if version_in_osv_range(version, event_map, scheme=scheme):
                matched = True
        except VersionSchemeError:
            return False, "unsupported_version_scheme", False
    if listed and not matched:
        return False, ",".join(descriptions) or "listed_versions", True
    if matched:
        return True, ",".join(descriptions), True
    if not any_supported_range and not listed:
        return False, "feed_unsupported", True
    return False, ",".join(descriptions), True


def _event_text(events: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for event in events:
        for key in ("introduced", "fixed", "last_affected", "limit"):
            if key in event:
                parts.append(f"{key}={event[key]}")
    return ";".join(parts)
