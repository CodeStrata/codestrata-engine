# Signed export projections and export modes (E13.3 / M32)

**Policy:** `engine-export-projection-policy:1.0`  
**Original schema:** `codestrata.export-original.v1`  
**Projection schema:** `codestrata.export-projection.v1` (`1.0.0`)  
**Verification profile:** `codestrata.export-projection.local-hmac.v1`

Headless invocation selects an explicit export mode. Redaction never rewrites
the local original. A separate projection lists the original digest, allowed
and withheld categories, the export-policy version, and operational signature
metadata that is not part of the canonical body.

| Mode | CLI | Allowed | Withheld | Transfer |
| --- | --- | --- | --- | --- |
| full | `--mode full` | evidence, graph | none | still local-only from this CLI |
| restricted | `--mode restricted --withhold CATEGORY` | complement | listed | still local-only from this CLI |
| no-export | `--mode no-export` (alias `none`) | none | evidence, graph | none |

`codestrata telemetry export` is headless: no prompt, no collector call,
`transmission_performed` is always false. Local analysis keeps working.

## Original vs projection

1. Seal the original canonical body and digest it.
2. HMAC-SHA256 the original bytes with a purpose-bound local test key.
   Signature metadata stays beside the body.
3. Project a **new** document. The original `canonical_bytes` are compared
   before and after; mutation fails.
4. Sign the projection separately. A projection cannot list withheld or
   unseen categories as `externally_verified_categories`.

Missing original evidence is `unavailable`. An untrusted key is `unverified`.
Wrong purpose (preview key/package used as production) is `wrong_purpose`.
An expired `validity_not_after` is `stale`. Tampered bytes or signatures are
`tampered` / `rejected`.

This local HMAC profile is **not** public Sigstore. E14.1 owns public
package/release verification. Private key material never appears in manifests
or logs.

## Fake collector receipts

`FakeCollector.revoke` / `expire` / `evaluate_receipt` exercise revoked and
expired receipts in-process. `server_deletion_performed` and
`server_admission_performed` stay false. Actual server deletion/admission is
follow-on work.

## Not this story

- Community API, S3, or infrastructure edits
- Public Sigstore / official release signing (E14.1)
- Live v2 collector admission or server-side deletion
