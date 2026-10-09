"""GitHub Actions branch-filter matching and push-pattern extraction."""

from __future__ import annotations

import re
from collections.abc import Sequence

_LIST_ITEM = re.compile(r"^-\s+(.+)$")


def github_ref_matches(pattern: str, ref: str) -> bool:
    """Match a branch name against a GitHub ``on.push.branches`` glob.

    ``*`` matches inside one path segment. ``**`` matches across ``/``.
    """

    if not pattern:
        return False
    escaped = re.escape(pattern)
    escaped = escaped.replace(r"\*\*", "\x00")
    escaped = escaped.replace(r"\*", r"[^/]*")
    escaped = escaped.replace("\x00", ".*")
    return re.fullmatch(escaped, ref) is not None


def any_glob_matches(patterns: Sequence[str], ref: str) -> bool:
    return any(github_ref_matches(pattern, ref) for pattern in patterns)


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _on_block(text: str) -> str:
    match = re.search(r"^on:\s*\n", text, re.MULTILINE)
    if match is None:
        inline = re.search(r"^on:\s*(\S.+)$", text, re.MULTILINE)
        return inline.group(1) if inline else ""
    start = match.end()
    lines: list[str] = []
    for line in text[start:].splitlines():
        if line and not line.startswith((" ", "\t")) and not line.startswith("#"):
            break
        lines.append(line)
    return "\n".join(lines)


def extract_push_branch_patterns(text: str) -> tuple[str, ...] | None:
    """Return push branch globs.

    ``None`` means there is no ``push`` trigger. An empty tuple means ``push``
    with no branch filter (GitHub runs the workflow on every branch).
    """

    inline = re.search(r"^on:\s*\[([^\]]+)\]", text, re.MULTILINE)
    if inline:
        items = {_unquote(part) for part in inline.group(1).split(",") if part.strip()}
        if "push" in items:
            return ()
        return None

    on_block = _on_block(text)
    if not on_block:
        return None
    if not re.search(r"^\s*push\b", on_block, re.MULTILINE):
        return None

    mapping = re.search(
        r"^  push:\s*\n((?:    .*\n?)*)",
        on_block + "\n",
        re.MULTILINE,
    )
    if mapping is None:
        return ()
    body = mapping.group(1)
    if "branches:" not in body:
        return ()
    inline_list = re.search(r"^    branches:\s*\[([^\]]*)\]", body, re.MULTILINE)
    if inline_list:
        return tuple(_unquote(part) for part in inline_list.group(1).split(",") if part.strip())
    listed: list[str] = []
    in_list = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("branches:"):
            in_list = True
            continue
        if in_list:
            item = _LIST_ITEM.match(stripped)
            if item:
                listed.append(_unquote(item.group(1)))
                continue
            if stripped and not stripped.startswith("#"):
                break
    return tuple(listed)
