"""Parse unified Git patches without applying them."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from codestrata.domain.contracts.serialization import digest_canonical

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_INDEX = re.compile(r"^index ([0-9a-f]{4,40})\.\.([0-9a-f]{4,40})")
_GIT_DIFF = re.compile(r"^diff --git a/(.*) b/(.*)$")


@dataclass(frozen=True, slots=True)
class PatchHunk:
    path: str
    old_path: str | None
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    added_lines: int
    deleted_lines: int
    header: str


@dataclass(frozen=True, slots=True)
class PatchFileFact:
    path: str
    old_path: str | None
    status: str
    added_lines: int | None
    deleted_lines: int | None
    binary: bool
    old_oid: str | None
    new_oid: str | None
    hunks: tuple[PatchHunk, ...]


@dataclass(frozen=True, slots=True)
class ParsedPatch:
    files: tuple[PatchFileFact, ...]
    patch_digest: str
    claimed_old_oids: tuple[str, ...]
    malformed: bool
    limitations: tuple[str, ...]


def parse_unified_patch(text: str) -> ParsedPatch:
    """Extract changed-line facts from a unified diff. Does not apply the patch."""

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if not text.strip():
        return ParsedPatch(
            files=(),
            patch_digest=digest,
            claimed_old_oids=(),
            malformed=True,
            limitations=("empty_patch",),
        )

    files: list[PatchFileFact] = []
    limitations: list[str] = []
    current_path: str | None = None
    old_path: str | None = None
    status = "modified"
    binary = False
    old_oid: str | None = None
    new_oid: str | None = None
    hunks: list[PatchHunk] = []
    added = 0
    deleted = 0
    in_hunk = False
    hunk_added = 0
    hunk_deleted = 0
    hunk_meta: tuple[int, int, int, int, str] | None = None
    claimed: list[str] = []
    malformed = False

    def flush() -> None:
        nonlocal current_path, old_path, status, binary, old_oid, new_oid, hunks, added, deleted
        if current_path is None:
            return
        if binary:
            added_count: int | None = None
            deleted_count: int | None = None
            limitations.append("binary_partial_size")
        else:
            added_count = added
            deleted_count = deleted
        files.append(
            PatchFileFact(
                path=current_path,
                old_path=old_path if old_path and old_path != current_path else None,
                status=status,
                added_lines=added_count,
                deleted_lines=deleted_count,
                binary=binary,
                old_oid=old_oid,
                new_oid=new_oid,
                hunks=tuple(hunks),
            )
        )
        current_path = None
        old_path = None
        status = "modified"
        binary = False
        old_oid = None
        new_oid = None
        hunks = []
        added = 0
        deleted = 0

    def close_hunk() -> None:
        nonlocal in_hunk, hunk_meta, hunk_added, hunk_deleted, added, deleted
        if not in_hunk or hunk_meta is None or current_path is None:
            in_hunk = False
            hunk_meta = None
            hunk_added = 0
            hunk_deleted = 0
            return
        old_start, old_count, new_start, new_count, header = hunk_meta
        hunks.append(
            PatchHunk(
                path=current_path,
                old_path=old_path,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                added_lines=hunk_added,
                deleted_lines=hunk_deleted,
                header=header,
            )
        )
        added += hunk_added
        deleted += hunk_deleted
        in_hunk = False
        hunk_meta = None
        hunk_added = 0
        hunk_deleted = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        git_header = _GIT_DIFF.match(line)
        if git_header:
            close_hunk()
            flush()
            old_path = git_header.group(1)
            current_path = git_header.group(2)
            status = "modified"
            continue
        if line.startswith("rename from "):
            old_path = line[len("rename from ") :]
            status = "renamed"
            continue
        if line.startswith("rename to "):
            current_path = line[len("rename to ") :]
            status = "renamed"
            continue
        if line.startswith("new file mode"):
            status = "added"
            continue
        if line.startswith("deleted file mode"):
            status = "deleted"
            continue
        if line.startswith("GIT binary patch") or line.startswith("Binary files "):
            binary = True
            close_hunk()
            continue
        index_match = _INDEX.match(line)
        if index_match:
            old_oid = index_match.group(1)
            new_oid = index_match.group(2)
            if old_oid and set(old_oid) != {"0"}:
                claimed.append(old_oid)
            continue
        hunk_match = _HUNK.match(line)
        if hunk_match:
            close_hunk()
            in_hunk = True
            hunk_meta = (
                int(hunk_match.group(1)),
                int(hunk_match.group(2) or "1"),
                int(hunk_match.group(3)),
                int(hunk_match.group(4) or "1"),
                line,
            )
            hunk_added = 0
            hunk_deleted = 0
            continue
        if in_hunk:
            if line.startswith("\\"):
                continue
            if line.startswith("+"):
                hunk_added += 1
            elif line.startswith("-"):
                hunk_deleted += 1
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if line.startswith("diff ") and current_path is None:
            malformed = True

    close_hunk()
    flush()
    if not files:
        malformed = True
        limitations.append("unparsed_patch")
    return ParsedPatch(
        files=tuple(files),
        patch_digest=digest,
        claimed_old_oids=tuple(dict.fromkeys(claimed)),
        malformed=malformed,
        limitations=tuple(dict.fromkeys(limitations)),
    )


def parsed_patch_canonical(parsed: ParsedPatch) -> str:
    payload = {
        "patch_digest": parsed.patch_digest,
        "malformed": parsed.malformed,
        "files": [
            {
                "path": item.path,
                "old_path": item.old_path,
                "status": item.status,
                "added_lines": item.added_lines,
                "deleted_lines": item.deleted_lines,
                "binary": item.binary,
                "old_oid": item.old_oid,
                "new_oid": item.new_oid,
                "hunks": [
                    {
                        "path": hunk.path,
                        "old_start": hunk.old_start,
                        "old_count": hunk.old_count,
                        "new_start": hunk.new_start,
                        "new_count": hunk.new_count,
                        "added_lines": hunk.added_lines,
                        "deleted_lines": hunk.deleted_lines,
                        "header": hunk.header,
                    }
                    for hunk in item.hunks
                ],
            }
            for item in parsed.files
        ],
    }
    return digest_canonical(payload)
