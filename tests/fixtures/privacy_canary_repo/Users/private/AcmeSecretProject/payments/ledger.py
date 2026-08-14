"""AcmeInternalSettlementEngine — local-only canary module (tests)."""

SECRET = "TEST_SECRET_DO_NOT_TRANSMIT"
PACKAGE = "acme-internal-payments-sdk"
REMOTE = "git@github.com:private/acme-secret.git"
URL = "https://internal.acme.example/private"


def settle() -> str:
    return SECRET
