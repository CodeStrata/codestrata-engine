# Offline release verification example (E14.1)

This example is local and offline. It does not publish, tag, or call Sigstore.

Policy: `engine/src/codestrata/resources/release/verification-profiles-v1.yaml`

- Public distribution uses profile `codestrata.release.sigstore-public.v1`
  with expected identity/issuer from that file.
- Private results use `codestrata.release.offline-self-managed-key.v1`.
  Do not attach a Rekor/tlog entry. Revocation lists have a freshness limit
  (7 days); they do not claim instant revocation.

Independent cryptographic fixtures used by Engine tests live under
`engine/tests/application/release/fixtures/verification/`.
