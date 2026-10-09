"""Parse live registry evidence. Never copy pyproject or git tags as the version."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from verification.live_release_baseline.install import (
    hashed_install_argv,
    hashed_requirements_line,
    interpret_rollback,
)
from verification.live_release_baseline.models import (
    ArtifactKind,
    CheckStatus,
    ContainerInquiry,
    DistributedFile,
    GitIdentity,
    InferenceError,
    InstallAttempt,
    InstallRollbackEvidence,
    LiveReleaseRecord,
    PublisherStatus,
    PyPIProject,
    R01Inventory,
    WorkflowSurface,
)
from verification.live_release_baseline.publisher import evaluate_r01

RECORDED_FILENAME = "recorded.yaml"


def default_recorded_path() -> Path:
    return Path(__file__).resolve().parent / RECORDED_FILENAME


def parse_pypi_project(payload: Mapping[str, object]) -> PyPIProject:
    """Live version comes from the PyPI JSON body, not local packaging metadata."""

    info = payload.get("info")
    if not isinstance(info, Mapping):
        raise InferenceError("PyPI payload missing info; cannot infer a live version")
    name = str(info.get("name") or "").strip()
    live_version = str(info.get("version") or "").strip()
    releases = payload.get("releases")
    if not isinstance(releases, Mapping) or not releases:
        urls = payload.get("urls")
        if not isinstance(urls, list) or not urls or not live_version:
            raise InferenceError(
                "PyPI payload has no releases/urls; refusing to use pyproject or tags"
            )
        files = _files_from_urls(urls)
        return PyPIProject(
            name=name or "unknown",
            live_version=live_version,
            versions=(live_version,),
            files=files,
            yanked=bool(info.get("yanked")),
        )
    versions = tuple(sorted(str(key) for key in releases.keys()))
    if not live_version or live_version not in releases:
        raise InferenceError(
            "PyPI info.version is missing from releases; refusing tag/pyproject fallback"
        )
    files = _files_from_urls(releases[live_version])
    if not files:
        raise InferenceError(f"PyPI version {live_version} has no distributable files")
    return PyPIProject(
        name=name or "unknown",
        live_version=live_version,
        versions=versions,
        files=files,
        yanked=bool(info.get("yanked")),
    )


def _files_from_urls(urls: object) -> tuple[DistributedFile, ...]:
    if not isinstance(urls, list):
        return ()
    files: list[DistributedFile] = []
    for item in urls:
        if not isinstance(item, Mapping):
            continue
        digests = item.get("digests")
        sha256 = ""
        if isinstance(digests, Mapping):
            sha256 = str(digests.get("sha256") or "")
        packagetype = str(item.get("packagetype") or "")
        files.append(
            DistributedFile(
                filename=str(item.get("filename") or ""),
                packagetype=packagetype,
                sha256=sha256,
                size=int(item.get("size") or 0),
                url=str(item.get("url") or ""),
                yanked=bool(item.get("yanked")),
            )
        )
    return tuple(files)


def refuse_pyproject_inference(
    *,
    pypi: PyPIProject | None,
    pyproject_version: str,
) -> None:
    """A local version string is never the live registry version."""

    if pypi is None:
        raise InferenceError(
            f"no live PyPI project; refusing to treat pyproject {pyproject_version!r} as released"
        )
    if pyproject_version and pyproject_version != pypi.live_version:
        # Allowed: they may diverge. Callers must keep using pypi.live_version.
        return
    if not pypi.files:
        raise InferenceError("PyPI listing has no files; refusing pyproject inference")


def unused_git_tags(pypi: PyPIProject, tags: Sequence[str]) -> tuple[str, ...]:
    live = f"v{pypi.live_version}"
    unused: list[str] = []
    for tag in tags:
        name = tag if tag.startswith("v") else f"v{tag}"
        if name != live:
            unused.append(tag)
    return tuple(unused)


def load_recorded(path: Path | None = None) -> LiveReleaseRecord:
    payload = yaml.safe_load((path or default_recorded_path()).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise InferenceError("recorded.yaml must be a mapping")
    pypi_raw = payload.get("pypi")
    if not isinstance(pypi_raw, Mapping):
        raise InferenceError("recorded.yaml missing pypi evidence")
    files = tuple(
        DistributedFile(
            filename=str(item["filename"]),
            packagetype=str(item["packagetype"]),
            sha256=str(item["sha256"]),
            size=int(item["size"]),
            url=str(item["url"]),
            yanked=bool(item.get("yanked", False)),
        )
        for item in pypi_raw.get("files") or []
        if isinstance(item, Mapping)
    )
    if not files:
        raise InferenceError("recorded.yaml pypi.files is empty")
    pypi = PyPIProject(
        name=str(pypi_raw["name"]),
        live_version=str(pypi_raw["live_version"]),
        versions=tuple(str(item) for item in pypi_raw.get("versions") or ()),
        files=files,
        yanked=bool(pypi_raw.get("yanked", False)),
    )
    refuse_pyproject_inference(
        pypi=pypi,
        pyproject_version=str(payload.get("pyproject_version_ignored") or ""),
    )
    identities = tuple(
        GitIdentity(
            repository=str(item["repository"]),
            ref=str(item["ref"]),
            sha=str(item["sha"]),
            kind=ArtifactKind(str(item["kind"])),
            notes=str(item.get("notes") or ""),
        )
        for item in payload.get("git_identities") or []
        if isinstance(item, Mapping)
    )
    containers = tuple(
        ContainerInquiry(
            registry=str(item["registry"]),
            repository=str(item["repository"]),
            status=CheckStatus(str(item["status"])),
            digest=str(item["digest"]) if item.get("digest") else None,
            http_status=int(item["http_status"]) if item.get("http_status") is not None else None,
            notes=str(item.get("notes") or ""),
        )
        for item in payload.get("containers") or []
        if isinstance(item, Mapping)
    )
    r01_raw = payload.get("r01")
    if not isinstance(r01_raw, Mapping):
        raise InferenceError("recorded.yaml missing r01")
    workflows = tuple(
        WorkflowSurface(
            path=str(item["path"]),
            name=str(item["name"]),
            triggers=tuple(str(t) for t in item.get("triggers") or ()),
            contents_write=bool(item.get("contents_write")),
            id_token_write=bool(item.get("id_token_write")),
            aws_oidc=bool(item.get("aws_oidc")),
            pypi_oidc_publish=bool(item.get("pypi_oidc_publish")),
            container_publish=bool(item.get("container_publish")),
            marketplace_publish=bool(item.get("marketplace_publish")),
            engine_only_publish=bool(item.get("engine_only_publish")),
            notes=tuple(str(n) for n in item.get("notes") or ()),
        )
        for item in r01_raw.get("workflows") or []
        if isinstance(item, Mapping)
    )
    computed = evaluate_r01(workflows)
    recorded_status = PublisherStatus(str(r01_raw["status"]))
    if recorded_status is not computed.status:
        raise InferenceError(
            f"recorded R01 status {recorded_status} disagrees with workflow inventory "
            f"{computed.status}"
        )
    r01 = R01Inventory(
        status=computed.status,
        reason=str(r01_raw.get("reason") or computed.reason),
        workflows=workflows,
        engine_only_oidc_publisher=str(r01_raw["engine_only_oidc_publisher"])
        if r01_raw.get("engine_only_oidc_publisher")
        else None,
        required_outside_engine_change=str(
            r01_raw.get("required_outside_engine_change") or computed.required_outside_engine_change
        ),
    )
    wheel = next((item for item in pypi.files if item.packagetype == "bdist_wheel"), None)
    expected_sha = wheel.sha256 if wheel is not None else ""
    install = _load_install(
        payload.get("install_rollback"),
        expected_version=pypi.live_version,
        expected_sha256=expected_sha,
    )
    return LiveReleaseRecord(
        inspected_at=str(payload.get("inspected_at") or ""),
        pypi=pypi,
        git_identities=identities,
        containers=containers,
        r01=r01,
        install_rollback=install,
        notes=tuple(str(item) for item in payload.get("notes") or ()),
        pyproject_version_ignored=str(payload["pyproject_version_ignored"])
        if payload.get("pyproject_version_ignored") is not None
        else None,
        tags_not_used_as_live=tuple(
            str(item) for item in payload.get("tags_not_used_as_live") or ()
        ),
    )


def _load_install(
    raw: object,
    *,
    expected_version: str,
    expected_sha256: str,
) -> InstallRollbackEvidence | None:
    if not isinstance(raw, Mapping):
        return None

    def _attempt(key: str) -> InstallAttempt:
        item = raw.get(key)
        if not isinstance(item, Mapping):
            raise InferenceError(f"install_rollback.{key} missing")
        return InstallAttempt(
            argv=tuple(str(part) for part in item.get("argv") or ()),
            exit_code=int(item["exit_code"]),
            stdout=str(item.get("stdout") or ""),
            stderr=str(item.get("stderr") or ""),
            installed_version=str(item["installed_version"])
            if item.get("installed_version") is not None
            else None,
            observed_sha256=str(item["observed_sha256"])
            if item.get("observed_sha256") is not None
            else None,
        )

    evidence = InstallRollbackEvidence(
        install=_attempt("install"),
        uninstall=_attempt("uninstall"),
        reinstall=_attempt("reinstall"),
        status=CheckStatus(str(raw["status"])),
        notes=tuple(str(item) for item in raw.get("notes") or ()),
    )
    interpreted = interpret_rollback(
        install=evidence.install,
        uninstall=evidence.uninstall,
        reinstall=evidence.reinstall,
        expected_version=str(raw.get("expected_version") or expected_version),
        expected_sha256=str(raw.get("expected_sha256") or expected_sha256),
    )
    if interpreted.status is not evidence.status:
        raise InferenceError(
            f"recorded install status {evidence.status} disagrees with "
            f"interpreted {interpreted.status}"
        )
    return evidence


def render_baseline(record: LiveReleaseRecord) -> str:
    files = "\n".join(
        f"| `{item.filename}` | `{item.packagetype}` | `{item.sha256}` | {item.size} |"
        for item in record.pypi.files
    )
    identities = "\n".join(
        (
            f"| `{item.repository}` | `{item.ref}` | `{item.sha}` | "
            f"`{item.kind.value}` | {item.notes} |"
        )
        for item in record.git_identities
    )
    container_rows: list[str] = []
    for item in record.containers:
        http_display = item.http_status if item.http_status is not None else "n/a"
        digest = item.digest or "none"
        container_rows.append(
            f"| `{item.registry}` | `{item.repository}` | `{item.status.value}` | "
            f"`{digest}` | {http_display} | {item.notes} |"
        )
    containers = "\n".join(container_rows)
    workflows = "\n".join(
        f"| `{item.path}` | `{item.name}` | {', '.join(item.triggers) or 'none'} | "
        f"{'yes' if item.id_token_write else 'no'} | "
        f"{'yes' if item.aws_oidc else 'no'} | "
        f"{'yes' if item.pypi_oidc_publish else 'no'} | "
        f"{'yes' if item.engine_only_publish else 'no'} |"
        for item in record.r01.workflows
    )
    install_block = "_not recorded_"
    if record.install_rollback is not None:
        rb = record.install_rollback
        install_block = (
            f"Status: **{rb.status.value}**\n\n"
            f"| Step | Exit | Version | SHA-256 |\n"
            f"|---|---|---|---|\n"
            f"| install | {rb.install.exit_code} | `{rb.install.installed_version}` | "
            f"`{rb.install.observed_sha256}` |\n"
            f"| uninstall | {rb.uninstall.exit_code} | `{rb.uninstall.installed_version}` | "
            f"`{rb.uninstall.observed_sha256}` |\n"
            f"| reinstall | {rb.reinstall.exit_code} | `{rb.reinstall.installed_version}` | "
            f"`{rb.reinstall.observed_sha256}` |\n\n" + "\n".join(f"- {note}" for note in rb.notes)
        )
    wheel = next((item for item in record.pypi.files if item.packagetype == "bdist_wheel"), None)
    if wheel is not None:
        argv = " ".join(hashed_install_argv(wheel))
        pin = hashed_requirements_line(wheel)
        install_cmd = f"{argv}\n# hashes file body:\n{pin}"
    else:
        install_cmd = "unavailable"
    notes = "\n".join(f"- {note}" for note in record.notes)
    tags = ", ".join(f"`{tag}`" for tag in record.tags_not_used_as_live) or "_none_"
    return f"""# Live Engine artifact and release route (E00.1)

This file records **inspected live registry and workflow evidence**.
It is not a release authorization. Package revision `ENGINE-2026-09-15-R1`.

Inspected: `{record.inspected_at}`.

Local `engine/pyproject.toml` version `{record.pyproject_version_ignored}` was
**not** used as the live version. Git tags {tags} were **not** used as the live
version.

## PyPI (`{record.pypi.name}`)

| | |
|---|---|
| Live version | `{record.pypi.live_version}` |
| Yanked | `{record.pypi.yanked}` |
| Known published versions | {", ".join(f"`{v}`" for v in record.pypi.versions)} |
| Project | https://pypi.org/project/{record.pypi.name}/{record.pypi.live_version}/ |

| File | Type | SHA-256 | Bytes |
|---|---|---|---|
{files}

Pinned install of the live wheel (isolated venv, never the working checkout):

```text
{install_cmd}
```

## Git identities (stable vs next)

| Repository | Ref | SHA | Kind | Notes |
|---|---|---|---|---|
{identities}

## Container / OCI

No verified public Engine container digest. A 401 from GHCR is **unavailable**,
not proof of absence.

| Registry | Repository | Status | Digest | HTTP | Notes |
|---|---|---|---|---|---|
{containers}

## R01 — authorized publisher

**Status: {record.r01.status.value}**

{record.r01.reason}

Engine-only OIDC publisher workflow: `{record.r01.engine_only_oidc_publisher or "none"}`.

Required outside-Engine change (not performed in E00.1):

{record.r01.required_outside_engine_change}

| Path | Name | Triggers | OIDC | AWS | PyPI | Engine-only |
|---|---|---|---|---|---|---|
{workflows}

Ordinary push to `release/**` still runs validation-only `ci.yml`. This story
did not edit workflows, the export manifest, or remotes.

## Install / rollback of the live artifact

{install_block}

## Notes

{notes}
"""


def write_baseline(record: LiveReleaseRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_baseline(record), encoding="utf-8", newline="\n")
