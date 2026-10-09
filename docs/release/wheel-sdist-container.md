# Standalone wheel, sdist and non-root container (E14.2)

Package revision `ENGINE-2026-09-15-R1`.

## Deliverables

- Build verifier: `python -m verification.release_build`
- Library API: `codestrata.application.release.standalone`
- Packaged policy:
  - `resources/release/runtime-lock-v1.txt`
  - `resources/release/headless-runtime-limits-v1.yaml`
  - `resources/release/packaging-inventory-v1.yaml`
- Container recipe: `examples/non-root-container/`

## Acceptance mapping

| Requirement | Mechanism |
|---|---|
| Wheel/sdist outside checkout | `run_build_verification` installs wheel in temp dir under parent of `engine/` |
| No PYTHONPATH / DB for smoke | `install_verify.scrubbed_environ` and version-only smoke |
| SBOM for runtime deps | `build_runtime_sbom` + CycloneDX JSON export |
| Provenance/checksums | `ReleaseProvenanceManifest` binds wheel/sdist/SBOM digests and an explicit source binding. A development binding omits `source_sha`. A committed binding requires a caller-supplied 40-hex SHA. The builder does not search parent directories for Git. |
| Container qualification | Recipe below. A missing Docker daemon is not a PASS. |
| Public source vs wheel inclusion | Separate `verify_public_source_export`, `verify_wheel_inventory`, `verify_sdist_inventory` |
| Headless measured limits | `bind_headless_operational_limits` ties packaged budgets to E01.1 ratification |
| Health/status file protocol | `LocalHealthStatus` written to `codestrata-local-health.json` |
| Retention / bounded audit | `retention_config`, `BoundedOperationalAudit` |
| SIGINT/SIGTERM grace + hard kill | `run_with_signal_supervision` |
| Container limits | `examples/non-root-container/docker-compose.yml` |

Official OIDC publication preflight is documented in `publication-preflight.md`
(E14.4). Headless detached result signing and consumer interop are documented
in `headless-consumer-interop.md` (E14.3).

## Source identity and container procedure

`ENGINE-2026-09-15-R1` remains the E01.1 catalog revision. It is not the
0.3.0 source SHA. Provenance records `catalog_package_revision` separately
from `source_binding`.

Pass `verified_source_sha` to `run_build_verification` only after the source
tree is a clean commit and that 40-hex SHA was verified for that tree. Omit
it for a dirty or isolated snapshot. The function does not walk parent
directories for a Git repository and does not copy an unrelated HEAD.

The local container recipe is `examples/non-root-container/Dockerfile`. Its
header says it is not a publisher. From `engine/`:

```bash
docker build -f examples/non-root-container/Dockerfile -t codestrata-engine:local .
docker run --rm codestrata-engine:local --version
```

`docker-compose.yml` in that directory runs `--version` with no network, a
non-root user, and a mounted output directory. Qualification requires the
Docker daemon and a recorded image digest. If the daemon is unavailable, the
container check stays blocked.
