# Privacy Policy (CodeStrata Community Edition)

**Product:** CodeStrata Engine (Community Edition) and related Community clients  
**Telemetry schema:** `1.0.0`  
**Default:** Anonymous telemetry is **disabled**

## What we collect (only if you opt in)

When you explicitly enable anonymous telemetry, CodeStrata may send:

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

## What we never collect

- Source code
- Repository names or URLs
- Git remotes
- File names or filesystem paths
- Findings, recommendations, or report contents
- AI prompts or AI responses
- Credentials, secrets, tokens, or API keys
- Hostname, username, email, or Git identity

## Opt-in process

Telemetry is **off by default**. On first interactive run you may see:

```text
Enable anonymous telemetry? [y/N]
```

The default answer is **No**. After you choose, CodeStrata will not ask again
until you reset.

You can also enable explicitly:

```bash
codestrata telemetry enable
```

## Disable instructions

```bash
codestrata telemetry disable
```

Environment override (forces off):

```bash
export CODESTRATA_TELEMETRY=0
```

## Reset instructions

Resets the anonymous installation ID, preferences, and local event queue
(telemetry returns to disabled; you may be asked again):

```bash
codestrata telemetry reset
```

State is stored under `~/.codestrata/` (override with `CODESTRATA_HOME` for
tests).

## Local queue

If a telemetry endpoint is unavailable, events are queued locally and retried
later. Queuing **never blocks** assessments.

Optional endpoint:

```bash
export CODESTRATA_TELEMETRY_ENDPOINT=https://example.invalid/v1/telemetry
```

When unset, events remain local-only (inspectable via `telemetry show` /
queue files under `~/.codestrata/`).

## Status

```bash
codestrata telemetry status
```

## Contact

Report privacy concerns privately using the process in `SECURITY.md` (GitHub
Security Advisories when enabled). Do not open public issues that include
secrets or private repository details.

## Related documentation

- `docs/telemetry.md` (Engine)
- `https://docs.codestrata.ai/security/privacy`
- Telemetry JSON Schema: `schemas/telemetry/codestrata.io/v1.0/TelemetryEvent.json`
