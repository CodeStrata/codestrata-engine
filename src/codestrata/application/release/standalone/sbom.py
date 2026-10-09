"""Runtime SBOM generation from pinned lock inputs."""

from __future__ import annotations

import json
import re

from codestrata import __version__
from codestrata.application.release.standalone.digest import sha256_bytes
from codestrata.application.release.standalone.models import RuntimeSbom, SbomComponent
from codestrata.application.release.standalone.policy import runtime_lock_text

_LINE = re.compile(r"^([A-Za-z0-9_.-]+)(.+)$")


def _parse_lock_lines(text: str) -> tuple[SbomComponent, ...]:
    components: list[SbomComponent] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE.match(stripped)
        if not match:
            continue
        name = match.group(1)
        version_spec = match.group(2).strip()
        purl = f"pkg:pypi/{name}@{version_spec.replace(',', '')}"
        components.append(
            SbomComponent(name=name, version_spec=version_spec, purl=purl),
        )
    return tuple(components)


def build_runtime_sbom() -> RuntimeSbom:
    components = _parse_lock_lines(runtime_lock_text())
    if not components:
        raise ValueError("runtime lock produced no SBOM components")
    return RuntimeSbom(
        components=components,
        metadata={
            "component": {
                "type": "application",
                "name": "codestrata",
                "version": __version__,
            }
        },
    )


def sbom_digest(sbom: RuntimeSbom) -> str:
    payload = sbom.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def cyclonedx_document(sbom: RuntimeSbom) -> dict[str, object]:
    """Minimal CycloneDX 1.5 document for resolved runtime dependencies."""

    components = [
        {
            "type": "library",
            "name": item.name,
            "version": item.version_spec,
            "purl": item.purl,
        }
        for item in sbom.components
    ]
    return {
        "bomFormat": sbom.bom_format,
        "specVersion": sbom.spec_version,
        "version": 1,
        "metadata": sbom.metadata,
        "components": components,
    }
