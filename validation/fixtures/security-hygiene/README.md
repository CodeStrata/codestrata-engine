# Security hygiene fixture (validation only)

Purpose-built CodeStrata validation fixture for **Security** precision checks.

## Intentional signals (fake / test-only)

These files contain **deliberate, non-functional** patterns the scanner should treat as security-relevant signals:

| Path | Signal |
|------|--------|
| `config/app.properties` | Placeholder credentials (`changeme`, fake `db_password`) |
| `secrets/test-only.pem` | Non-functional `BEGIN PRIVATE KEY` block with `TEST_ONLY_NONFUNCTIONAL_PRIVATE_KEY_MATERIAL_DO_NOT_USE` body |
| `src/app.py` | Minimal source file so language inventory has content to scan |

## Negative controls (should not look like literal secrets)

These files exercise **false-positive resistance**: common patterns that mention secrets, passwords, or keys without embedding real credentials:

| Path | Pattern |
|------|---------|
| `.github/workflows/ci.yml` | GitHub Actions `${{ secrets.API_TOKEN }}` reference only |
| `docs/examples.md` | Documentation example `password=example` |
| `tests/fixtures/fake_secret.txt` | Labeled fixture line `password=test_only_fixture_value` |
| `config/safe-env-ref.properties` | Property `api_key=${API_KEY}` — env var reference, no literal value |

## Safety

- **No real secrets**
- **No valid credentials**
- **No usable private-key material**
- Values are labeled TEST-ONLY and cannot authenticate anywhere
- Fixture must not execute harmful behavior (static files only)

This is **not** a customer example application. Do not copy these patterns into production code.
