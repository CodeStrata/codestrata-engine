"""Parse GitHub Actions workflow text without treating ``on:`` as YAML bool."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from verification.live_release_baseline.models import WorkflowSurface

_NAME = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
_TRIGGER_KEY = re.compile(r"^  ([A-Za-z_][\w-]*):", re.MULTILINE)

_PYPI_PUBLISH = (
    "pypa/gh-action-pypi-publish",
    "twine upload",
    "pypi-publish",
)
_CONTAINER_PUBLISH = (
    "docker push",
    "docker/build-push-action",
    "ghcr.io/",
    "cosign sign",
)
_MARKETPLACE = (
    "vsce publish",
    "ovsx publish",
    "marketplace publish",
)
_AWS_OIDC = (
    "aws-actions/configure-aws-credentials",
    "sts.amazonaws.com",
    "role-to-assume",
)


def _unquoted(value: str) -> str:
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


def parse_triggers(text: str) -> tuple[str, ...]:
    block = _on_block(text)
    if not block:
        return ()
    if "\n" not in block and block.strip() and not block.strip().endswith(":"):
        return (block.strip().strip("[] ").replace('"', ""),)
    keys = [_unquoted(item) for item in _TRIGGER_KEY.findall(block)]
    return tuple(keys)


def _has_any(haystack: str, needles: Iterable[str]) -> bool:
    lowered = haystack.lower()
    return any(needle.lower() in lowered for needle in needles)


def _without_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def parse_workflow_text(path: str, text: str) -> WorkflowSurface:
    name_match = _NAME.search(text)
    name = _unquoted(name_match.group(1)) if name_match else Path(path).stem
    body = _without_comments(text)
    id_token_write = bool(re.search(r"id-token:\s*write", body))
    contents_write = bool(re.search(r"contents:\s*write", body))
    pypi = _has_any(body, _PYPI_PUBLISH)
    container = _has_any(body, _CONTAINER_PUBLISH) and (
        "docker push" in body.lower() or "build-push-action" in body.lower()
    )
    notes: list[str] = []
    if "marketplace publish is intentionally not invoked" in text.lower():
        notes.append("marketplace publish explicitly not invoked")
    if "does not: publish" in text.lower() or "does NOT: publish" in text:
        notes.append("header forbids publish")
    engine_only = pypi and "engine" in body.lower() and "platform/" not in body.lower()
    if pypi and not engine_only:
        notes.append("pypi publish markers are not Engine-only")
    return WorkflowSurface(
        path=path.replace("\\", "/"),
        name=name,
        triggers=parse_triggers(text),
        contents_write=contents_write,
        id_token_write=id_token_write,
        aws_oidc=_has_any(body, _AWS_OIDC),
        pypi_oidc_publish=pypi and id_token_write,
        container_publish=container,
        marketplace_publish=_has_any(body, _MARKETPLACE),
        engine_only_publish=bool(engine_only and pypi and id_token_write),
        notes=tuple(notes),
    )


def load_root_workflows(repo_root: Path) -> tuple[WorkflowSurface, ...]:
    """GitHub Actions only loads the monorepo root ``.github/workflows/``."""

    directory = repo_root / ".github" / "workflows"
    if not directory.is_dir():
        return ()
    surfaces: list[WorkflowSurface] = []
    for path in sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml")):
        if path.name.lower() == "readme.md":
            continue
        relative = path.relative_to(repo_root).as_posix()
        surfaces.append(parse_workflow_text(relative, path.read_text(encoding="utf-8")))
    return tuple(surfaces)
