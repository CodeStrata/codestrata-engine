# Non-interactive telemetry prompt suppression (Slice 9.5)

**Policy:** `community-telemetry-non-interactive-policy:1.0`  
**Decision when suppressed:** `non_interactive_disabled` + `non_interactive_policy`  
**Scope:** current CLI process only — not saved

## Principle

No prompt is safer than an ambiguous prompt.

A telemetry consent prompt must never appear in automation, machine-readable
execution, piped execution, CI, or any environment where an interactive answer
cannot be safely and deliberately supplied.

Uncertainty **suppresses** the prompt. Suppression means telemetry remains
disabled. Suppression is **not** explicit user denial unless the user actually
saw and answered the prompt.

## What “non-interactive” means

Execution is treated as non-interactive (prompt suppressed) when any of the
following hold:

| Condition | Suppression reason | Decision |
| --------- | ------------------ | -------- |
| stdin is not a TTY | `stdin_not_interactive` | `non_interactive_disabled` |
| stdin missing / closed / probe failure | `stdin_unavailable` | `non_interactive_disabled` |
| piped / redirected stdin (non-TTY) | `piped_input` or `stdin_not_interactive` | `non_interactive_disabled` |
| `CI` or reviewed automation markers | `ci_detected` / `automation_detected` | `non_interactive_disabled` |
| `--json-summary` (machine-readable) | `machine_readable_output` | `non_interactive_disabled` |
| `--quiet` on eligible commands | `quiet_mode` | `non_interactive_disabled` |
| output not suitable for a prompt | `output_not_interactive` | `non_interactive_disabled` |
| help / version / about | `help_or_version` | `disabled_by_default` |
| shell completion helpers | `shell_completion` | `disabled_by_default` |
| telemetry inspection / other excluded | `command_excluded` | `disabled_by_default` |
| command not `assess` | `command_not_eligible` | `disabled_by_default` |
| explicit session consent already set | `explicit_decision_present` | keep explicit decision |

Product-policy exclusions use `disabled_by_default` — they are **not** silently
classified as `non_interactive_disabled`.

## TTY and piped input

Preferred eligibility requires:

- stdin is a TTY
- output is suitable for a prompt (not quiet / not JSON summary)
- not CI / automation
- command is `assess`
- no prior prompt / no explicit decision

Piped examples (`echo y | codestrata assess …`, `cat input.txt | …`):

- **no** telemetry prompt
- telemetry does **not** read stdin (does not steal application input)
- decision: `non_interactive_disabled`
- primary command continues normally

Missing or closed stdin / `isatty` failures: suppress, disable telemetry, continue
the primary command — no stack trace.

## Automation detection

Centralized presence checks (values never recorded):

- `CI` in `{1,true,yes,on}`
- `CODESTRATA_CLI_MACHINE` (existing machine-mode marker)
- a small reviewed set: `GITHUB_ACTIONS`, `GITLAB_CI`, `JENKINS_URL`,
  `BUILD_BUILDID`, `TEAMCITY_VERSION`, `TF_BUILD`, `CODEBUILD_BUILD_ID`,
  `BUILDKITE`, `CIRCLECI`, `TRAVIS`

Diagnostics expose only `automation_detected: true|false` — never provider names,
job IDs, or environment values.

`stdin_interactive=True` alone **cannot** bypass automation detection.
Focused tests inject `automation_detected=False` (internal construction parameter).
There is **no** public bypass environment variable.

## Explicit decision precedence

If an explicit session consent is already supplied (internal factory / future
CLI flags in Slice 9.6):

- do **not** prompt
- do **not** replace the decision with `non_interactive_disabled`
- allow remains allow; deny remains deny
- suppression reason: `explicit_decision_present`

## Prompt attempts

Non-interactive suppression is **not** a prompt attempt:

- `prompted=false`
- `attempts=0`
- process still locks so later hooks cannot unexpectedly prompt mid-command

Prompt **failure** (after the prompt was shown) remains distinct: attempts ≥ 1,
safe deny/default, primary command continues.

## Runtime factory

```python
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
)

facade, prompt_result = create_command_session_telemetry_runtime(
    command="assess",
    # production: detectors run automatically
)
```

Flow: explicit consent? → command eligible? → non-interactive policy →
interactive prompt if eligible → one runtime/facade.

Does **not** read preferences, identity, queue, or endpoint configuration.

## Guarantees

- no prompt text on stdout in machine-readable / quiet / CI paths
- no preference / identity / queue / HTTP / installation ID
- no persistence; no prior-consent reuse; legacy prefs ignored
- fail closed for telemetry (detector failures suppress)
- assessment report schema, artifacts, and exit codes unchanged
- no `--telemetry-allow` / `--telemetry-deny` in this slice

## Not yet available

- Status: [telemetry-status.md](telemetry-status.md)
- Public catalog: [telemetry-event-catalog.md](telemetry-event-catalog.md)
- Preview: [telemetry-preview.md](telemetry-preview.md)
- Community Cloud HTTP transport

Automation-safe explicit consent is available via `--telemetry-allow` /
`--telemetry-deny` on `assess` — see
[telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md).

## Related

- [telemetry-status.md](telemetry-status.md)
- [telemetry-cli-consent-flags.md](telemetry-cli-consent-flags.md)
- [telemetry-interactive-consent.md](telemetry-interactive-consent.md)
- [telemetry-session-consent.md](telemetry-session-consent.md)
- [telemetry-disabled-default.md](telemetry-disabled-default.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [telemetry.md](telemetry.md)
- [../PRIVACY.md](../PRIVACY.md)
