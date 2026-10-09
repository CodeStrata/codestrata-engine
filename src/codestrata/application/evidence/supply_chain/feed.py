"""Pinned offline OSV snapshot loader. Never fetches the network."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from codestrata.application.evidence.supply_chain.models import FeedFreshness, FreshnessStatus

PROVIDER_ID = "osv.dev"
PROVIDER_NAME = "OSV (osv-vulnerabilities snapshot)"
FRESHNESS_MAX_AGE = timedelta(days=7)
FEED_SCHEMA = "osv.dev/snapshot/v1"


class FeedError(ValueError):
    """Pinned OSV snapshot is missing, corrupt, or requests a live lookup."""


def _stable_dumps(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def snapshot_digest(advisories: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_stable_dumps(advisories).encode("utf-8")).hexdigest()


def parse_iso_time(value: str | None, *, label: str) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise FeedError(f"{label} is not an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class OsvSnapshot:
    """Normalized pinned OSV records. No HTTP client is imported or called."""

    def __init__(
        self,
        *,
        path: Path | None,
        payload: dict[str, Any],
        digest: str,
    ) -> None:
        self.path = path
        self.payload = payload
        self.digest = digest
        self.provider_id = str(payload.get("provider_id") or PROVIDER_ID)
        self.published_at = str(payload.get("published_at") or payload.get("updated_at") or "")
        self.updated_at = str(payload.get("updated_at") or self.published_at)
        self.license = str(payload.get("license") or "")
        raw = payload.get("advisories") or payload.get("vulnerabilities") or []
        if not isinstance(raw, list):
            raise FeedError("snapshot advisories must be a list")
        self.advisories: list[dict[str, Any]] = [item for item in raw if isinstance(item, dict)]

    @property
    def advisory_count(self) -> int:
        return len(self.advisories)


def load_osv_snapshot(path: Path | None) -> OsvSnapshot | None:
    """Load a local JSON snapshot. ``None`` means the cache is absent."""

    if path is None:
        return None
    rendered = str(path).replace("\\", "/")
    if rendered.startswith(("http://", "https://", "http:", "https:")) or "://" in rendered:
        raise FeedError("live OSV lookup is forbidden")
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FeedError(f"corrupt OSV snapshot: {error}") from error
    if not isinstance(payload, dict):
        raise FeedError("OSV snapshot must be an object")
    if payload.get("url") or payload.get("endpoint"):
        raise FeedError("snapshot must not request a live endpoint")
    advisories = payload.get("advisories") or payload.get("vulnerabilities") or []
    if not isinstance(advisories, list):
        raise FeedError("snapshot advisories must be a list")
    digest = str(
        payload.get("digest")
        or snapshot_digest([item for item in advisories if isinstance(item, dict)])
    )
    return OsvSnapshot(path=path, payload=payload, digest=digest)


def load_osv_snapshot_payload(payload: dict[str, Any] | None) -> OsvSnapshot | None:
    if payload is None:
        return None
    if payload.get("url") or payload.get("endpoint"):
        raise FeedError("snapshot must not request a live endpoint")
    advisories = payload.get("advisories") or payload.get("vulnerabilities") or []
    if not isinstance(advisories, list):
        raise FeedError("snapshot advisories must be a list")
    digest = str(
        payload.get("digest")
        or snapshot_digest([item for item in advisories if isinstance(item, dict)])
    )
    return OsvSnapshot(path=None, payload=payload, digest=digest)


def evaluate_freshness(
    snapshot: OsvSnapshot | None,
    *,
    evaluation_time: datetime,
) -> FeedFreshness:
    if evaluation_time.tzinfo:
        pinned = evaluation_time.astimezone(UTC)
    else:
        pinned = evaluation_time.replace(tzinfo=UTC)
    eval_text = pinned.isoformat().replace("+00:00", "Z")
    if snapshot is None:
        return FeedFreshness(
            status=FreshnessStatus.UNKNOWN,
            reason="feed_missing",
            evaluation_time=eval_text,
            cannot_prove_clean=True,
        )
    published = parse_iso_time(snapshot.updated_at or snapshot.published_at, label="feed time")
    if published is None:
        return FeedFreshness(
            status=FreshnessStatus.UNKNOWN,
            reason="source_time_missing",
            provider_id=snapshot.provider_id,
            snapshot_digest=snapshot.digest,
            evaluation_time=eval_text,
            cannot_prove_clean=True,
        )
    age = pinned - published
    age_seconds = int(age.total_seconds())
    published_text = published.isoformat().replace("+00:00", "Z")
    if age > FRESHNESS_MAX_AGE:
        return FeedFreshness(
            status=FreshnessStatus.STALE,
            reason="feed_stale",
            provider_id=snapshot.provider_id,
            snapshot_digest=snapshot.digest,
            published_at=published_text,
            evaluation_time=eval_text,
            age_seconds=max(age_seconds, 0),
            cannot_prove_clean=True,
        )
    return FeedFreshness(
        status=FreshnessStatus.FRESH,
        reason="feed_fresh",
        provider_id=snapshot.provider_id,
        snapshot_digest=snapshot.digest,
        published_at=published_text,
        evaluation_time=eval_text,
        age_seconds=max(age_seconds, 0),
        cannot_prove_clean=False,
    )
