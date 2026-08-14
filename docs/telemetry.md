# Anonymous telemetry (Community Edition)

**Default:** Disabled  
**Product authority (v0.2.1):** https://docs.codestrata.ai/reference/telemetry

CodeStrata Community telemetry is **privacy-first**: privacy-preserving /
pseudonymous where an installation id is used, minimal, versioned, and
**explicit opt-in only**.

> **Epic 20 (current product contract):** Durable Engine consent under
> `CODESTRATA_HOME` is shared by CLI and VS Code.
>
> - **Undecided / Disabled** → no Community collection
> - **Legacy v1 Yes** → lifecycle usage telemetry only (never silently expanded)
> - **v2 Yes** (`codestrata telemetry enable` or interactive Allow) → lifecycle
>   usage + privacy-safe **assessment_metadata** (schemas 1.0 + 1.1)
> - `--telemetry-allow` is a **session bridge only** — not consent; cannot invent
>   Yes or override Disabled
> - Report publish is a separate explicit action
>
> Historical Slice 9.x–10.x construction notes below remain for engineering
> archaeology; if they conflict with the product authority page, the Docs page
> wins.

> **Epic 9 Slice 9.1–9.11:** The Engine **telemetry runtime** is authoritative for
> normal CLI/assessment paths and is disabled by default with **no transmission**
> until consent permits. Eligible interactive `assess` runs may prompt when
> undecided (default No). CI, pipes, quiet/JSON, and other non-interactive
> contexts never prompt — see [telemetry-non-interactive.md](telemetry-non-interactive.md).
> Explicit `--telemetry-allow` / `--telemetry-deny` on `assess` provide
> automation-safe session bridging — see
> [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md). Status:
> [telemetry-status.md](telemetry-status.md). Public event-and-field catalog:
> [telemetry-event-catalog.md](telemetry-event-catalog.md) /
> [telemetry-event-catalog.json](telemetry-event-catalog.json). Illustrative
> preview: [telemetry-preview.md](telemetry-preview.md). Pre-transport privacy:
> [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md).
> Fail-silent HTTP transport (explicit; unavailable by default):
> [telemetry-transport.md](telemetry-transport.md).
> Assessment isolation: [telemetry-assessment-isolation.md](telemetry-assessment-isolation.md).
> Also: [telemetry-runtime.md](telemetry-runtime.md),
> [telemetry-disabled-default.md](telemetry-disabled-default.md),
> [telemetry-session-consent.md](telemetry-session-consent.md), and
> [telemetry-interactive-consent.md](telemetry-interactive-consent.md).
> **Slice 9.14** cross-client verification (Engine ↔ VS Code principles, independent
> schemas): [`../../verification/privacy_first_telemetry/README.md`](../../verification/privacy_first_telemetry/README.md).
> **Slice 9.15** Epic 9 completion:
> [`../../verification/privacy_first_telemetry_completion/README.md`](../../verification/privacy_first_telemetry_completion/README.md).
> **Epic 9 is complete** for v0.2.0: privacy-first runtimes exist; default telemetry
> remains disabled until durable consent.
> **Epic 10 Slice 10.1** defines the anonymous analytics **contract only**
> ([telemetry-anonymous-analytics.md](telemetry-anonymous-analytics.md)) — no
> collection, persistence, or transmission.
> **Epic 10 Slice 10.2** adds local anonymous installation identity
> ([telemetry-installation-identity.md](telemetry-installation-identity.md)) —
> unused operationally until runtime analytics.
> **Epic 10 Slice 10.3** adds local runtime analytics construction
> ([telemetry-runtime-analytics.md](telemetry-runtime-analytics.md)) — no
> transmission; analytics payloads are not persisted.
> **Epic 10 Slice 10.4** adds assessment analytics construction APIs
> ([telemetry-assessment-analytics.md](telemetry-assessment-analytics.md)) —
> construction-only; not wired into assess; no transmission or analytics
> persistence.
> **Epic 10 Slice 10.5** adds repository aggregate analytics construction APIs
> ([telemetry-repository-aggregate-analytics.md](telemetry-repository-aggregate-analytics.md)).
>
> **Epic 10 Slice 10.6** adds AI analytics construction APIs
> ([telemetry-ai-analytics.md](telemetry-ai-analytics.md)) — local, unwired,
> no transmission or analytics persistence.
> — language/rule aggregates only; unwired; no transmission.
> **Slice 10.8** verifies Epic 10 privacy guarantees
> ([`../../verification/anonymous_analytics_privacy/README.md`](../../verification/anonymous_analytics_privacy/README.md)).
> **Slice 10.9** verifies Epic 10 completion
> ([`../../verification/anonymous_analytics_completion/README.md`](../../verification/anonymous_analytics_completion/README.md)) —
> contracts-only; production analytics collection remains **not operational**.
> This page also describes the Phase 14.3 `TelemetryService` / CLI preference commands
> historical surface. `codestrata telemetry show`
> remains the legacy sample-payload command; use `preview` for privacy-first
> examples.

## Principles

| Principle | Behavior |
| --------- | -------- |
| Disabled by default | No events leave the machine until you opt in |
| Explicit opt-in | Interactive prompt defaults to **No**; or `codestrata telemetry enable` (v2) |
| Transparent | `codestrata telemetry preview` / `show` print illustrative payload shapes |
| Pseudonymous installation id | Random UUID v4 under `CODESTRATA_HOME` — not machine-derived |
| Minimal | Bands, categories, and privacy-safe aggregates only — never source or repository identity |
| Non-blocking | Fail-silent transport; assessments never wait on network |

## Commands

```bash
codestrata telemetry status
codestrata telemetry status --json
codestrata telemetry preview
codestrata telemetry enable
codestrata telemetry disable
codestrata telemetry reset
codestrata telemetry show
```

Use `preview` for privacy-first illustrative transport-safe events. Use `show`
only for legacy compatibility sample payloads.

## FAQ

**Is telemetry on after install?**  
No.

**Does enable turn on assessment insights?**  
Yes — `enable` persists **v2** (usage + privacy-safe assessment insights).

**Does `--telemetry-allow` create consent?**  
No — session bridge only.

**Can I inspect payloads?**  
Yes — `codestrata telemetry preview` / `show`.

**How do I turn it off forever on this machine?**  
`codestrata telemetry disable`.

See also: [PRIVACY.md](../PRIVACY.md).
