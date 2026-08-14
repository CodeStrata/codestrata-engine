# Privacy Policy (CodeStrata Community Edition)

**Product:** CodeStrata Engine (Community Edition) and related Community clients  
**Authoritative published page:** https://docs.codestrata.ai/security/privacy  
**Default:** Community collection is **disabled**

This file summarizes Engine-local privacy posture. The published docs page is
the canonical Community / Engine product privacy authority.

## Product consent (authoritative for `assess`)

| Topic | Detail |
| --- | --- |
| Default | Disabled / undecided — no Community collection |
| Opt in (interactive) | Eligible interactive assess may prompt when undecided; Yes → **v2** (usage + assessment insights) |
| Opt in (explicit) | `codestrata telemetry enable` → **v2 Yes** |
| Opt out | `codestrata telemetry disable` |
| Session bridge | `--telemetry-allow` does **not** create consent and cannot override Disabled |
| Non-interactive / CI | Never prompts; durable v2 may emit approved streams without prompting |
| Persistence | Engine-owned preference under `CODESTRATA_HOME` (shared with VS Code) |

Consent authorizes privacy-safe transmission eligibility. It is **not**
permission to publish reports. After durable **v2 Yes**, production Community
HTTP targets `https://api.codestrata.ai` when
`CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL` is set; otherwise transport stays
unavailable.

**Legacy v1:** lifecycle-only consent is never silently expanded to assessment
intelligence — users are asked before broader v2 scope.

Assessments and local reports under `.codestrata-artifacts/` work with
collection off.

## Never collected through Community telemetry / assessment intelligence

Source code, file contents, snippets/evidence, absolute paths, repository
name/URL/remote, credentials/API keys, git user identity, finding prose,
exact internal package names, graph identifiers, prompts/responses, stack
traces, report ID/URL.

With **v2**, the Engine may send **privacy-safe aggregates** only (approved
rule ID + severity + category + count, head confidence, categorical
characteristics) — not individual rich findings.

A **random (pseudonymous) installation UUID** may be used for first/repeat
Insights analytics. Prefer that wording over absolute anonymity claims.

Full detail: https://docs.codestrata.ai/security/privacy  
Retention / deletion: https://docs.codestrata.ai/security/retention-and-deletion

## Status

```bash
codestrata telemetry status
codestrata telemetry status --json
```

## Contact

Report privacy concerns privately using the process in `SECURITY.md`.

## Related documentation

- https://docs.codestrata.ai/reference/telemetry
- https://docs.codestrata.ai/security/data-collection
- https://docs.codestrata.ai/security/privacy
- https://docs.codestrata.ai/architecture/community-cloud
- https://docs.codestrata.ai/architecture/insights
