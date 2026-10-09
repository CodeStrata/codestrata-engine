# Release-owner approval record (template)

**Do not treat this template as approval until completed and signed by the release owner.**

| Field | Value |
|---|---|
| Package revision | `ENGINE-2026-09-15-R1` |
| Candidate semver | `0.2.2` |
| Source Git SHA | _fill: G50/E16.1 freeze SHA_ |
| Release owner | _name_ |
| Authorization date (UTC) | _YYYY-MM-DD_ |
| R01 workflow | `.github/workflows/engine-pypi-release.yml` |
| PyPI project | `codestrata` |
| Rollback target (unchanged) | `0.2.1` per `baseline.md` |

## Approved artifact digests (SHA-256)

Fill from `verification.release_build` / `provenance.json` on the authorized commit **after** version bump:

| Artifact | SHA-256 | Bytes |
|---|---|---|
| Wheel | _fill_ | _fill_ |
| sdist | _fill_ | _fill_ |
| Runtime SBOM digest | _fill_ | _fill_ |

## Publish method

- [ ] GitHub Actions `engine-pypi-release` with `confirm_release=PUBLISH`
- [ ] Other (explain; must still satisfy R01 OIDC policy): _n/a_

## Post-publish verification (independent)

| Check | Result |
|---|---|
| PyPI lists `0.2.2` | _pending_ |
| Downloaded wheel hash matches table above | _pending_ |
| `codestrata version` reports `0.2.2` in clean venv | _pending_ |

## Sign-off

```text
Release owner: ___________________  Date: __________
I authorize publication of the digests above via the R01 route only.
```

Keep a copy under `engine/docs/release/` or linked ticket; redact secrets.
