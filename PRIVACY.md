# Privacy Policy (CodeStrata Community Edition)

**Product:** CodeStrata Engine (Community Edition) and related Community clients  
**Authoritative published page:** https://docs.codestrata.ai/security/privacy  
**Default:** Anonymous product telemetry is **disabled**

This file summarizes Engine-local privacy posture. The published docs page is
the canonical Community / Engine product privacy authority (local assessments,
telemetry, Data Lake, published reports, AI providers, retention, opt-out).

## Privacy-first product consent (authoritative for `assess`)

| Topic | Detail |
| --- | --- |
| Default | `disabled_by_default` — transmission unauthorized |
| Opt in (interactive) | Eligible interactive assess may prompt when preference is undecided; default **No** (`[y/N]`) |
| Opt in (explicit) | `codestrata telemetry enable` or `codestrata assess --telemetry-allow` |
| Opt out (explicit) | `codestrata telemetry disable` or `codestrata assess --telemetry-deny` |
| Non-interactive / CI | Never prompts; decision is `non_interactive_disabled` |
| Persistence | Explicit Yes/No is stored locally under `CODESTRATA_HOME`; undecided remains disabled |

Consent authorizes privacy-safe transmission eligibility. It is **not**
permission to publish reports, and it is **not** required for voluntary
public-report Yes/No feedback. After explicit opt-in, production Community HTTP
transport targets `https://api.codestrata.ai` when
`CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL` is set; otherwise transport stays
unavailable. Disabled / denied / non-interactive sessions never open HTTP
transport.

Assessments and local reports under `.codestrata-artifacts/` work with telemetry
off. Local artifacts do not automatically become Cloud telemetry or public
reports.

## Local assessment artifacts

```text
.codestrata-artifacts/assessments/<repository_id>/{current,previous}/
.codestrata-artifacts/intelligence/<portfolio_id>/{current,previous}/
```

Typical assessment files: `assessment.json`, `assessment.html`, `heads/`.

## Never collected through Community telemetry

Source code, file contents, full HTML/JSON reports, findings/evidence/EIR
bodies, absolute paths, credentials/API keys, git user identity, AI prompts or
responses. The privacy-first assess runtime does not use `installation_id`;
some Community API stream contracts may accept one when present for analytics
dedup.

Full detail: https://docs.codestrata.ai/security/privacy

## Status

```bash
codestrata telemetry status
```

## Contact

Report privacy concerns privately using the process in `SECURITY.md` (GitHub
Security Advisories when enabled). Do not open public issues that include
secrets or private repository details.

## Related documentation

- https://docs.codestrata.ai/architecture/community-cloud (Community Cloud architecture)
- https://docs.codestrata.ai/architecture/data-lake (Data Lake)
- https://docs.codestrata.ai/architecture/insights (Insights)
- https://docs.codestrata.ai/security/source-locality (what stays local vs leaves)
- https://docs.codestrata.ai/ai-providers/ (optional AI enrichment data flow)
- https://docs.codestrata.ai/reference/telemetry (canonical Telemetry)
- https://docs.codestrata.ai/security/data-collection (canonical Data Collection)
- https://docs.codestrata.ai/security/collected-fields (field inventory)
- https://docs.codestrata.ai/security/retention-and-deletion (retention / opt-out / revoke)
- https://docs.codestrata.ai/security/privacy (canonical Community Privacy)
- `docs/telemetry.md` (Engine-local notes)
- `docs/ai-provider-security-boundaries.md` (Epic 11 provider privacy / failure isolation)
- Telemetry JSON Schema: `schemas/telemetry/codestrata.io/v1.0/TelemetryEvent.json`

---

## Legacy preference CLI (compatibility only)

> The sections below describe the existing opt-in `TelemetryService` /
> `codestrata telemetry enable|disable` preference commands. They are
> **compatibility-only** and do **not** authorize the privacy-first assess
> runtime.

**Telemetry schema:** `1.0.0` (legacy `TelemetryService`)  
**Runtime / consent policies:** see Engine `docs/telemetry-*.md` and Epic 9–10
verification under `verification/privacy_first_telemetry/` and
`verification/anonymous_analytics_privacy/`.

### What legacy opt-in may collect

When you explicitly enable anonymous telemetry via the legacy preference path,
CodeStrata may send:

- A random installation ID (UUID v4)
- CodeStrata version, OS family, and Python version
- Command name (for example `assess`, `open`)
- Enabled assessment domain categories (not findings)
- Language categories (for example `python`, `java`) — never filenames
- Repository size **band** and duration **band** (never exact counts)
- Whether optional AI was enabled/used (never prompts or responses)
- Success or failure flags
- Event timestamps

Events are versioned (`schema_version: 1.0.0`). Inspect any payload with:

```bash
codestrata telemetry show
```

### Legacy enable / disable

```bash
codestrata telemetry enable
codestrata telemetry disable
export CODESTRATA_TELEMETRY=0
codestrata telemetry reset
```

State is stored under `~/.codestrata/` (override with `CODESTRATA_HOME` for
tests). Legacy preferences do **not** authorize privacy-first assess
transmission.

### Local queue (legacy path)

If a legacy telemetry endpoint is unavailable, events may be queued locally and
retried later. Queuing **never blocks** assessments.

Optional endpoint:

```bash
export CODESTRATA_TELEMETRY_ENDPOINT=https://example.invalid/v1/telemetry
```

When unset, events remain local-only (inspectable via `telemetry show` /
queue files under `~/.codestrata/`).
