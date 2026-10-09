# Publication plan — Community Engine 0.2.2 (E16.2)

Package revision `ENGINE-2026-09-15-R1`.

**This document is a reviewable publication plan only.** It is not release-owner
authorization and does not permit PyPI upload until R01 is merged and configured.
Operational steps: **`E16.2-unblock-checklist.md`**. Proposed R01 workflow:
`.github/workflows/engine-pypi-release.yml` (monorepo; requires admin merge + PyPI
Trusted Publishing).

## Authorization checklist (all required before live publish)

| Requirement | Status (2026-09-30) | Evidence |
|---|---|---|
| G50 PASS on frozen candidate | **PASS** | `engine/docs/implementation/gates/G50.md`; candidate SHA below |
| E16.1 freeze with qualified digests | **PASS** | `engine/docs/release/release-candidate-freeze.md` |
| E15.3 release gate on candidate | **PASS** | `release_gate` exit 0 on integration lineage |
| R01 — Engine-only OIDC publisher | **BLOCKED** | `engine/docs/release/baseline.md`; `r01-preflight.json` from preflight |
| Release-owner written approval (version, digests, registries, route) | **Absent** | No signed approval record in Engine docs |
| Independent engineer review of P51 ledger | **Pending** | `engine/docs/implementation/gates/E16.2.md` |

## Qualified candidate identity (publish these bytes, not an arbitrary local build)

| Field | Value |
|---|---|
| Git SHA | `ae08622dd28c08c12351e3fe51229aacf85047e8` |
| Target semver | `0.2.2` (not on PyPI; live rollback remains `0.2.1`) |
| `RULESET_VERSION` | `1.2.0` |
| G50 certified | Yes (reviewer Abhinav Bussa, 2026-09-30) |

Frozen artifact digests (from `release-candidate-freeze.md`, built on the SHA above):

| Artifact | SHA-256 | Bytes |
|---|---|---|
| Wheel (`codestrata-0.2.2-py3-none-any.whl` after version bump at publish) | `159ae99d41c0c5e4ad339d757b6e869e7fe503306ffbb19f0cbd5731de856f5a` | 2968123 |
| sdist | `c8cc2e52c25131bacc50942d9133bac5e9da14c928b2c808c67fe6c766f51e9d` | 2194853 |
| Runtime SBOM digest | `7baaddca4596196567327291b53b6148dadfa872a0deb19346ff13a675b33dff` | 1117 |

**Important:** Rebuild on the exact freeze SHA after bumping `engine/pyproject.toml` and
`codestrata.__version__` to `0.2.2`. The digests above were produced at freeze time with
version metadata still at `0.2.1` in tree; the release owner must record the **post-bump**
wheel/sdist digests in the approval record before upload. Do not upload a wheel built from
`release/engine-next` HEAD without reconciling to the G50-certified source tree.

## Live baseline (independent verification)

Rechecked PyPI JSON `https://pypi.org/pypi/codestrata/json` on **2026-09-30**:

| | |
|---|---|
| Live version | `0.2.1` only (no `0.2.2`) |
| Wheel SHA-256 | `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18` |
| sdist SHA-256 | `acd8615186977d9a62f3661f8a8d71fe2be380c371c9ea29048f1bb2cd1212e6` |

Rollback procedure: `engine/docs/release/baseline.md` and `release-candidate-freeze.md`.

## R01 — authorized Engine-only route (outside Engine code)

R01 remains **BLOCKED**. Monorepo workflows inspected 2026-09-30:

| Workflow | OIDC | PyPI publish | Engine-only |
|---|---|---|---|
| `.github/workflows/ci.yml` | no | no | no (validation only) |
| AWS infrastructure workflows | yes | no | no |

Required **separate** authorization (not performed in E16.2):

1. Add or enable a maintainer-controlled workflow that requests `id-token: write` and
   publishes **only** the Engine package via PyPI Trusted Publishing (or equivalent
   OIDC-constrained signer).
2. Ensure Community export policy still permits the publisher path (workflows excluded
   from mirror export cannot be “fixed” by adding `engine/.github/workflows/` alone).
3. Record workflow name, environment, PyPI project, and trusted-publisher binding in
   `baseline.md` when R01 closes.

Until then, maintainers may run **local** preflight only:

```bash
cd engine
git checkout ae08622dd28c08c12351e3fe51229aacf85047e8
# After authorized version bump to 0.2.2:
python -m verification.release_build --output .quality-runs/publish/release-build
python -m verification.publication_preflight --output .quality-runs/publish/publication-preflight
```

Preflight exit 0 proves rehearsal verification; `r01.status` must still be `BLOCKED`
until the workflow exists.

## Publication sequence (release owner, after authorization)

1. **Version cut (Engine repo, authorized commit on freeze lineage):** set `0.2.2` in
   `pyproject.toml`, `src/codestrata/__init__.py`, and `CHANGELOG.md` (release section
   from integrated P01–P50 scope; no implied Platform/Webapp changes).
2. **Build and digest lock:** `verification.release_build`; store `provenance.json`,
   SBOM, wheel, sdist; release approval must list exact SHA-256 for each blob.
3. **Signing / attestation:** use the authorized R01 OIDC route for live Sigstore
   bundles where required; offline rehearsal bundles from preflight are not substitutes
   for production attestations.
4. **Upload:** PyPI upload of wheel + sdist only for this semver; **no** bulk mirror
   publish, **no** forced `pip install --upgrade` campaign, **no** stable monorepo tag
   move unless separately approved.
5. **Independent download verify:** from a clean host, `pip download codestrata==0.2.2`
   (or hash-pinned URL), confirm digests match approval, run
   `codestrata version`, and optional signature verification per E14.3 docs.
6. **Handoff to E16.3:** smoke on **published** bytes only (P52); observation window
   starts after smoke passes.

## Explicit non-goals

- Platform, Webapp, VS Code, AWS deployment, or root workflow edits as part of P51.
- Publishing container images (no verified public digest in baseline).
- Replacing live `0.2.1` artifacts or reusing the `0.2.1` version string.
- Claiming success from a maintainer laptop build without R01 + approval + public verify.

## Consumer verification (post-publish)

After live `0.2.2` exists on PyPI:

```bash
python -m venv /tmp/codestrata-0.2.2-verify
# Windows: use a dedicated path under %TEMP%
/tmp/codestrata-0.2.2-verify/Scripts/pip install --no-deps codestrata==0.2.2
/tmp/codestrata-0.2.2-verify/Scripts/codestrata version
# Compare wheel hash to release approval record (not to this plan alone).
```

Detached signature / Sigstore verification steps: `engine/docs/release/publication-preflight.md`
and E14.3 headless interop documentation.
