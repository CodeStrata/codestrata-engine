# Per-session telemetry consent (Slice 9.3)

**Policy:** `community-telemetry-session-consent-policy:1.0`  
**Scope:** one CLI process / one `TelemetryRuntime`  
**Default:** `disabled_by_default` (no decision ≠ consent)

## What a “session” means

For Epic 9, one telemetry session is:

- one CLI **process** invocation
- one explicitly constructed `TelemetryRuntime`
- one consent decision shared by telemetry hooks inside that process
- **no** persistence after process exit
- **no** reuse in a later invocation

It is **not** a user account, installation lifetime, repository lifetime, shell
login, VS Code workspace, browser session, or persisted token.

## Consent principle

Consent is an affirmative, purpose-specific, **current-process** decision.

It must **not** be inferred from legacy preferences, previous CLI invocations,
installation identity, queues, `CODESTRATA_TELEMETRY_ENDPOINT`, TTY/CI state,
config files, network availability, prior runtime objects, or
`codestrata telemetry enable`.

No decision means disabled. Explicit denial is distinct from default.

## Decisions and sources (Slices 9.3–9.5)

| Decision | Source | Explicit | Transmission authorized |
| -------- | ------ | -------- | ----------------------- |
| `disabled_by_default` | `default` | no | no |
| `allowed_for_session` | `explicit_session_allow`, `interactive_prompt`, or `cli_flag` | yes | yes |
| `denied_for_session` | `explicit_session_deny`, `interactive_prompt`, or `cli_flag` | yes | no |
| `non_interactive_disabled` | `non_interactive_policy` | no | no |

Reserved (not implemented here): none for Epic 9 preview/catalog. Catalog:
[telemetry-event-catalog.md](telemetry-event-catalog.md). Preview:
[telemetry-preview.md](telemetry-preview.md).
Status: [telemetry-status.md](telemetry-status.md).

`non_interactive_disabled` is **not** user consent. It means the prompt was
suppressed by the non-interactive policy. Explicit CLI flags map to `cli_flag`
— see [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md).
Inconsistent combinations raise `SessionConsentError` (no silent normalize).
See [telemetry-non-interactive.md](telemetry-non-interactive.md).

## Consent versus transport

`transmission_authorized=true` means the runtime **may** call the transport port
after privacy projection. It does **not** mean events were sent.

Default transport remains `UnavailableTelemetryTransport` → result `unavailable`,
never `sent`, no HTTP, no queue fallback, no installation ID.

Default and denied sessions **do not** invoke transport.

## Factories

```python
from codestrata.telemetry.consent import allow_session_consent, deny_session_consent
from codestrata.telemetry.runtime_factory import (
    create_default_telemetry_runtime,
    create_session_telemetry_runtime,
)

create_default_telemetry_runtime()  # always disabled_by_default

create_session_telemetry_runtime(consent=allow_session_consent())
create_session_telemetry_runtime(consent=deny_session_consent())
```

Consent is fixed at construction (no mutable enable/disable on the runtime).

Capture transport is **test-only** and must be injected explicitly.

## Normal CLI

`get_telemetry_service()` still defaults to a disabled facade. Eligible `assess`
invocations may prompt once when interactive; otherwise the non-interactive
policy suppresses the prompt. See
[telemetry-interactive-consent.md](telemetry-interactive-consent.md) and
[telemetry-non-interactive.md](telemetry-non-interactive.md).

Legacy `codestrata telemetry enable` does **not** create `allowed_for_session`
for normal product commands.

Explicit per-invocation flags on `assess`:

```bash
codestrata assess --repo . --telemetry-allow
codestrata assess --repo . --telemetry-deny
```

See [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md).

## Guarantees

- never persisted; never read from disk
- never generates/reads installation identity
- privacy projection cannot be bypassed by consent
- preview never transmits
- fail-silent; primary product results unchanged
- Process A allow does not authorize Process B default

## Related

- [telemetry-status.md](telemetry-status.md)
- [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- [telemetry-non-interactive.md](telemetry-non-interactive.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [telemetry-disabled-default.md](telemetry-disabled-default.md)
- [telemetry-interactive-consent.md](telemetry-interactive-consent.md)
- [telemetry.md](telemetry.md)
