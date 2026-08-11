# Security architecture notes

## Principles

1. **Deterministic analysis first** — no target-code execution.
2. **Least privilege defaults** — AI, MCP, Enterprise KG, knowledge features off unless enabled.
3. **Fail closed on path escapes** — reads outside the repository root are errors.
4. **Secrets by reference** — env var names in config, values never serialized.
5. **Community ≠ Platform** — public engine export excludes Enterprise KG runtime.

## Components

| Component | Security controls |
| --------- | ----------------- |
| Local scanner | Symlink-safe walk, exclusions, file-count cap |
| Content reader | Normalize relative paths; refuse symlink files; root bound |
| GitHub clone | Credential-free URL; askpass temp 0700; redacted errors |
| Config / profiles | Community defaults; effective dump redaction |
| Reports | Branding; no credential fields; path hygiene; customer-safe text projection (`customer_safe_text` / redaction) so PEM headers and secret-shaped values do not reach customer fields |
| MCP | Localhost; result size caps; mapping redaction; optional artifact paths off |
| Enterprise KG | Config-gated; omitted from Community export; extension hook preserved |

Customer-facing Finding / Recommendation text uses the Engine customer-safe text
contract (`codestrata.security.customer_safe_text`). Platform Engineering
Intelligence ingestion independently rejects unsafe customer fields — Engine
serialization must satisfy that gate without weakening it.

## Extension point

`codestrata.extensions.enterprise_runtime_available()` and the
`EnterpriseExtension` protocol allow Platform builds to supply Enterprise KG
without Community importing `platform/`.

## Automation

* `python scripts/security_check.py` — static checks (secrets, shell=True, unsafe YAML, etc.)
* `python scripts/validate-public-exports.py` — export hygiene
* `tests/architecture/` — engine↔platform boundary
* Dependency audit via `pip-audit` (see hardening checklist)
