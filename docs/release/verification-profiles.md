# Release verification profiles (E14.1)

Package revision `ENGINE-2026-09-15-R1`. This is not a public-signing
authorization (E14.4) and not result signing (E14.3).

Engine verifies **supplied** bundles locally. It does not call Fulcio, Rekor,
or any other network service. No-consent local utility is unchanged.

## Profiles

| Profile | Role | Algorithm | Transparency log |
|---|---|---|---|
| `codestrata.release.sigstore-public.v1` | `public_distribution` | ECDSA P-256 SHA-256 | Required. Hashedrekord of **digest + signature only** |
| `codestrata.release.offline-self-managed-key.v1` | `private_result` | Ed25519 | **Forbidden**. Private rule/result bytes never enter a public log |

Signer roles are distinct. A public-distribution artifact cannot be admitted
on the private profile, and a private result cannot be logged to Rekor.

## Public Sigstore checks

The verifier binds:

- expected identity (SAN URI, suffix `*` permitted)
- expected OIDC issuer (Fulcio OID `1.3.6.1.4.1.57264.1.1`)
- leaf certificate against a pinned trust root
- certificate expiry at pinned `evaluation_time`
- code-signing EKU
- ECDSA signature over the artifact bytes
- Rekor inclusion promise over the hashedrekord body

Wrong issuer, tampered signature/digest, expired certificate, unsupported
bundle media type/algorithm, and preview-for-production purpose are distinct
statuses. They are not collapsed into a mocked boolean.

## Private offline checks

The verifier binds a local trust store (`key_id`, public PEM, purpose, role)
and a revocation inventory with `last_updated`.

Revocation is **freshness-limited**, not instant:

- Inventory older than `max_age_seconds` (default 7 days) yields `stale`
  with reason `revocation_inventory_exceeds_freshness_limit`. The key is
  neither verified nor treated as revoked.
- `instant_revocation: true` is rejected.
- A key listed as revoked is `revoked` only when the inventory is fresh.

## Version and expiry

Package versions must be pinned. Production packages require
`validity_not_after`. Evaluation time is supplied as context; a clock is not
read from the canonical body.

## Packaged policy

`codestrata.resources/release/verification-profiles-v1.yaml`
(`engine-release-verification-profiles:1.0`).

Official OIDC publication rehearsal is documented in
[`publication-preflight.md`](./publication-preflight.md) (E14.4 / R01).
