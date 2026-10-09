# Official public signing and publication preflight (E14.4)

Package revision `ENGINE-2026-09-15-R1`. This is a **rehearsal**, not a release
authorization. No PyPI upload, container push, tag move, or notification is
performed.

## Maintainer runner

```bash
cd engine
python -m verification.publication_preflight --output .quality-runs/e14.4/publication-preflight
```

Library entrypoint: `codestrata.application.release.publication.run_publication_preflight`.

## What the preflight does

1. Runs the E14.2 build verifier (wheel, sdist, SBOM, provenance, clean install).
2. Writes a `publication-catalog.json` of candidate blob digests (wheel, sdist,
   SBOM, provenance, container recipe files, rehearsal Sigstore bundle).
3. Rehearses **offline** public Sigstore verification (E14.1 profile) against the
   candidate wheel using test Fulcio/Rekor material bound to the wheel SHA-256.
4. Records R01 publisher inventory from the monorepo root workflows.

## R01 and read-only CI

R01 remains **BLOCKED** until an authorized Engine-only GitHub Actions workflow
requests `id-token: write` and publishes Engine alone via PyPI Trusted Publishing
(or equivalent OIDC-constrained signer). Validation-only `ci.yml`, AWS
infrastructure OIDC, and workflows excluded from the Community export manifest
**cannot** satisfy R01. The preflight sets
`monorepo_ci_relabeled_as_publisher` if `ci.yml` is incorrectly treated as a
publisher.

When R01 is blocked, `required_outside_engine_change` records the exact
outside-Engine operation needed for separate authorization. Completing this
Engine code does not close E14.4 for live publication.

## Acceptance mapping

| Requirement | Mechanism |
|---|---|
| Candidate blobs + SBOM + provenance | E14.2 `run_build_verification` output under `--output` |
| OIDC identity + immutable digests | `build_rehearsal_verify_payload` + `verify_payload` (public profile) |
| Read-only CI not a publisher | `monorepo_ci_relabeled_as_publisher` + `evaluate_r01` inventory |
| No export-manifest bypass | No `engine/.github/workflows/` publisher; inventory documents denylist |
| Blocked R01 recorded | `r01-preflight.json` and summary `r01` block |

Official live OIDC publication remains gated on R01 closure (E16.2 / release owner).
