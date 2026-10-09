"""Bind artifact digests into a release provenance manifest."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Literal

from codestrata import __version__
from codestrata.application.release.standalone.digest import sha256_file
from codestrata.application.release.standalone.models import (
    ArtifactRecord,
    ReleaseProvenanceManifest,
    SourceBinding,
)
from codestrata.application.release.standalone.policy import (
    headless_runtime_limits_digest,
    operational_profile_id,
    runtime_lock_digest,
)
from codestrata.application.release.standalone.sbom import build_runtime_sbom, sbom_digest


def artifact_record(
    path: Path,
    *,
    kind: Literal["wheel", "sdist", "sbom", "provenance", "runtime_lock"],
) -> ArtifactRecord:
    data = path.read_bytes()
    return ArtifactRecord(
        kind=kind,
        filename=path.name,
        sha256=sha256_file(path),
        bytes=len(data),
    )


def development_source_binding(*, source_root: str) -> SourceBinding:
    """Label an unverified tree. No source SHA is invented."""

    return SourceBinding(
        status="development",
        source_sha=None,
        source_root=source_root,
        toolchain=f"Python {platform.python_version()}",
        build_procedure="codestrata.application.release.standalone.run_build_verification",
        note="development-only; source SHA is omitted until a clean commit is supplied",
    )


def committed_source_binding(*, source_sha: str, source_root: str) -> SourceBinding:
    """Bind a caller-verified clean commit. This function does not run Git."""

    return SourceBinding(
        status="committed",
        source_sha=source_sha,
        source_root=source_root,
        toolchain=f"Python {platform.python_version()}",
        build_procedure="codestrata.application.release.standalone.run_build_verification",
        note="caller verified this SHA on a clean source tree",
    )


def build_provenance_manifest(
    *,
    wheel: Path | None,
    sdist: Path | None,
    sbom_path: Path | None = None,
    source_binding: SourceBinding | None = None,
) -> ReleaseProvenanceManifest:
    sbom = build_runtime_sbom()
    digest = sbom_digest(sbom)
    records: list[ArtifactRecord] = []
    if wheel is not None and wheel.is_file():
        records.append(artifact_record(wheel, kind="wheel"))
    if sdist is not None and sdist.is_file():
        records.append(artifact_record(sdist, kind="sdist"))
    if sbom_path is not None and sbom_path.is_file():
        records.append(artifact_record(sbom_path, kind="sbom"))
    records.append(
        ArtifactRecord(
            kind="runtime_lock",
            filename="runtime-lock-v1.txt",
            sha256=runtime_lock_digest(),
            bytes=0,
        )
    )
    return ReleaseProvenanceManifest(
        engine_version=__version__,
        source_binding=source_binding or development_source_binding(source_root="unspecified"),
        artifacts=tuple(records),
        runtime_lock_digest=runtime_lock_digest(),
        operational_limits_profile_id=operational_profile_id(),
        operational_limits_digest=headless_runtime_limits_digest(),
        sbom_digest=digest,
    )
