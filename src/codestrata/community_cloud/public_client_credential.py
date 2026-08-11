"""Packaged Community public client credential (v0.2.0).

This is a **public Community client credential**, not a user secret and not an
AWS/operator credential. It authenticates Community Edition CLI/VS Code to
Community Cloud ingestion and report-publishing routes only.

Properties:
- Distributed with the Community Engine package
- Backend verifies fingerprint in Secrets Manager
- Rate-limited; revocable/rotatable by operators
- Does not grant Insights operator APIs, AWS access, or Secrets Manager access
- Override with ``CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL`` for operator/CI use

Never log or print this value in CLI user output.
"""

from __future__ import annotations

# Public Community client credential for codestrata_cli (packaged distribution).
# Fingerprint registered as cred-community-public-cli-v020.
_PUBLIC_COMMUNITY_CLIENT_CREDENTIAL = "cscc_v1_vTIc2ee8iQgj2AycSXmNnnEJU3fjyc40IFk7qnyC"

PUBLIC_CLIENT_ID = "client-community-public-cli-v020"
PUBLIC_CREDENTIAL_ID = "cred-community-public-cli-v020"
PUBLIC_CLIENT_DISTRIBUTION = "packaged_with_community_engine"


def packaged_public_community_client_credential() -> str:
    """Return the packaged public Community client credential string."""

    return _PUBLIC_COMMUNITY_CLIENT_CREDENTIAL
