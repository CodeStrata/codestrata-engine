# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes |

Older pre-release branches are unsupported unless noted in a GitHub Security
Advisory.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities, and
**do not disclose publicly** before coordinated release of a fix or advisory.

Report privately via:

* A private **GitHub Security Advisory** on the affected public repository
  (preferred when enabled), or
* The security contact listed on the repository’s GitHub profile / security
  policy page (no personal emails are published in this file)

Include:

* A description of the issue and its impact
* Steps to reproduce (proof of concept if available)
* Affected versions or commit SHAs if known
* Whether you plan coordinated disclosure timing preferences

You should receive an acknowledgment within **7 days**. We aim to provide a fix
or mitigation timeline within **30 days** for confirmed issues in supported
versions, then coordinate disclosure with you.

## Scope notes for CodeStrata

* Never commit secrets, tokens, or `.env` files.
* Configuration should reference credentials via environment variable names
  (`token_env`), not embed secret values.
* Reports and JSON artifacts must not include runtime credentials or absolute
  host paths that expose private environments.
* Community Edition **never executes** analyzed repository code and does not
  import target modules.
* External AI providers and Enterprise KG are **disabled by default**.

## Related documentation

* [Threat model](docs/security/threat-model.md) (includes hardening checklist)
* [Security architecture](docs/security/architecture.md)
* [MCP security](docs/mcp/security.md)
