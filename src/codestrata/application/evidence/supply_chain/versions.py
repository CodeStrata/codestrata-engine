"""Deterministic version comparison for OSV SEMVER and ECOSYSTEM ranges.

No package installation. Unsupported schemes stay UNKNOWN, never guessed.
Prerelease versions only match ranges that mention a prerelease on the same
major.minor.patch (npm/OSV SEMVER boundary).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)
_DOTTED = re.compile(r"^(?P<head>\d+(?:\.\d+)*)(?P<rest>[A-Za-z0-9.+_-]*)?$")
_NUMERIC = re.compile(r"^\d+$")


class VersionSchemeError(ValueError):
    """Version cannot be compared under the requested scheme."""


@dataclass(frozen=True)
class ParsedVersion:
    scheme: str
    numeric: tuple[int, ...]
    prerelease: tuple[str, ...]
    original: str

    @property
    def has_prerelease(self) -> bool:
        return bool(self.prerelease)


def is_exact_lock_version(text: str | None) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if any(token in value for token in ("<", ">", "*", "^", "~", " ", ",")):
        return False
    if value.startswith(("git+", "http://", "https://", "file:", "workspace:")):
        return False
    return True


def parse_version(text: str, *, scheme: str) -> ParsedVersion:
    value = text.strip()
    if not value:
        raise VersionSchemeError("empty version")
    if scheme == "SEMVER":
        match = _SEMVER.fullmatch(value)
        if match is None:
            raise VersionSchemeError(f"unsupported SEMVER: {value}")
        pre = match.group("pre")
        return ParsedVersion(
            scheme="SEMVER",
            numeric=(
                int(match.group("major")),
                int(match.group("minor")),
                int(match.group("patch")),
            ),
            prerelease=_split_pre(pre),
            original=value,
        )
    if scheme in {"ECOSYSTEM", "PEP440"}:
        return _parse_ecosystem(value)
    raise VersionSchemeError(f"unsupported scheme {scheme}")


def _split_pre(pre: str | None) -> tuple[str, ...]:
    if not pre:
        return ()
    return tuple(part for part in pre.split(".") if part)


def _parse_ecosystem(value: str) -> ParsedVersion:
    stripped = value.strip().lstrip("vV")
    if stripped.lower() in {"latest", "dev", "*"}:
        raise VersionSchemeError(f"unsupported ECOSYSTEM version: {value}")
    match = _DOTTED.match(stripped)
    if match is None:
        raise VersionSchemeError(f"unsupported ECOSYSTEM version: {value}")
    numeric = tuple(int(part) for part in match.group("head").split("."))
    rest = (match.group("rest") or "").lstrip(".-_+")
    pre: tuple[str, ...] = ()
    lowered = rest.lower()
    if lowered:
        if lowered.startswith(("a", "alpha", "b", "beta", "rc", "pre", "dev", "snapshot")):
            pre = tuple(part for part in re.split(r"[.+_-]", rest) if part)
        elif rest:
            # Trailing non-numeric junk that is not a known prerelease token.
            raise VersionSchemeError(f"unsupported ECOSYSTEM version: {value}")
    if len(numeric) < 1:
        raise VersionSchemeError(f"unsupported ECOSYSTEM version: {value}")
    return ParsedVersion(
        scheme="ECOSYSTEM",
        numeric=numeric,
        prerelease=pre,
        original=value,
    )


def compare(left: ParsedVersion, right: ParsedVersion) -> int:
    length = max(len(left.numeric), len(right.numeric))
    left_n = left.numeric + (0,) * (length - len(left.numeric))
    right_n = right.numeric + (0,) * (length - len(right.numeric))
    if left_n < right_n:
        return -1
    if left_n > right_n:
        return 1
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    for lpart, rpart in zip(left.prerelease, right.prerelease, strict=False):
        result = _compare_pre_part(lpart, rpart)
        if result:
            return result
    if len(left.prerelease) < len(right.prerelease):
        return -1
    if len(left.prerelease) > len(right.prerelease):
        return 1
    return 0


def _compare_pre_part(left: str, right: str) -> int:
    if _NUMERIC.fullmatch(left) and _NUMERIC.fullmatch(right):
        lnum, rnum = int(left), int(right)
        return (lnum > rnum) - (lnum < rnum)
    if _NUMERIC.fullmatch(left):
        return -1
    if _NUMERIC.fullmatch(right):
        return 1
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _geq(left: ParsedVersion, right: ParsedVersion) -> bool:
    return compare(left, right) >= 0


def _gt(left: ParsedVersion, right: ParsedVersion) -> bool:
    return compare(left, right) > 0


def version_in_osv_range(
    version: str,
    events: list[dict[str, str]],
    *,
    scheme: str,
) -> bool:
    """Evaluate OSV range events against an exact version.

    Prerelease boundary: a prerelease version is in-range only when at least
    one event version carries a prerelease on the same numeric tuple.
    """

    parsed = parse_version(version, scheme=scheme)
    if parsed.has_prerelease and not _prerelease_mentioned(parsed, events, scheme=scheme):
        return False
    affected = False
    for event in events:
        introduced = event.get("introduced")
        fixed = event.get("fixed")
        last_affected = event.get("last_affected")
        limit = event.get("limit")
        if introduced is not None:
            if introduced in {"", "0"} or _geq(parsed, parse_version(introduced, scheme=scheme)):
                affected = True
        if fixed:
            if _geq(parsed, parse_version(fixed, scheme=scheme)):
                affected = False
        if last_affected:
            if _gt(parsed, parse_version(last_affected, scheme=scheme)):
                affected = False
        if limit:
            if _geq(parsed, parse_version(limit, scheme=scheme)):
                affected = False
    return affected


def _prerelease_mentioned(
    version: ParsedVersion,
    events: list[dict[str, str]],
    *,
    scheme: str,
) -> bool:
    for event in events:
        for key in ("introduced", "fixed", "last_affected", "limit"):
            raw = event.get(key)
            if not raw or raw in {"", "0"}:
                continue
            try:
                parsed = parse_version(raw, scheme=scheme)
            except VersionSchemeError:
                continue
            if parsed.has_prerelease and parsed.numeric[:3] == version.numeric[:3]:
                return True
    return False
