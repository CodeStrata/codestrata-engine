# Headless consumer interoperability (E14.3)

Package revision `ENGINE-2026-09-15-R1`.

## Deliverables

- Neutral local runner: `codestrata.application.release.headless.run_headless_invocation`
- Schema-only consumer: `consume_headless_bundle`
- Detached Ed25519 result signatures via isolated signer process
- Maintainer verifier: `python -m verification.headless_interop`

## Separation

| Phase | Credentials | Network |
|---|---|---|
| Analysis runner | Must not read `CODESTRATA_HEADLESS_SIGNER_PEM` | Offline only |
| Detached signer child | Reads signer PEM from its env | None |

Export projections remain separate from canonical originals (E13.3). Hosted
lease, upload, admission persistence, and official OIDC publication remain
E14.4 / R04.

## Standard artifacts

Written under the invocation `output_path`:

- `EffectiveRuleSet.json`
- `admission.json`
- `operational-binding.json`
- `export-original.json` / `export-projection.json`
- `local-job-state.json`
- `headless-run-manifest.json`
- `detached-signature.json` (operational, not part of manifest digest list)

Operational health uses `codestrata-local-health.json` (file protocol from E14.2).
