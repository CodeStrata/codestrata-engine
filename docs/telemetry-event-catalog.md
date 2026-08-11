# Privacy-first telemetry event-and-field catalog

**Catalog ID:** `codestrata-privacy-first-telemetry-catalog`  
**Catalog schema:** `privacy-first-telemetry-catalog` `1.0.0`  
**Runtime event schema:** `1.0`  
**Runtime policy:** `1.0`  
**Catalog policy:** `1.0`  
**Client:** `codestrata_cli`  
**Transmission:** not operational  
**Installation identity:** not used  
**Consent scope:** session (persistence: none)  
**Consent expands fields:** no  
**Privacy filtering:** required

This catalog describes what the Engine privacy-first runtime **may**
project. Not every defined event is necessarily emitted today.
No privacy-first telemetry is transmitted because transport is unavailable.
Examples are illustrative and were not transmitted.

## Events

### `application_completed`

- **Purpose:** Marks successful or terminal completion of a CLI process lifecycle.
- **Lifecycle meaning:** Process completion (lifecycle may be complete).
- **Usage:** `supported_but_not_currently_emitted`
- **Transmission operational:** no
- **Required fields:** `client_name`, `event_type`, `runtime_policy_version`, `schema_version`
- **Optional fields:** `ai_used`, `arch_family`, `cli_version`, `duration_bucket`, `enabled_assessment_heads`, `failure_category`, `lifecycle`, `offline_mode`, `operation_category`, `os_family`, `result`
- **Prohibited fields:** Any field outside the approved allowlist is rejected. Forbidden identity/path/credential field names are rejected.
- **Constraints:** Shared event shape; no additional event-specific requiredness is enforced by current validators.
- **Privacy:** Privacy projection is mandatory. Consent cannot expand fields. Transport-bound events must pass the pre-transport privacy gate. Cloud mapping is independently versioned. Default transport remains unavailable; HTTP requires explicit configuration. installation_id and wire event_id are not Engine catalog fields.

Illustrative example:

```json
{
  "client_name": "codestrata_cli",
  "event_type": "application_completed",
  "runtime_policy_version": "1.0",
  "schema_version": "1.0"
}
```

### `application_started`

- **Purpose:** Marks the start of a CLI process lifecycle for privacy-safe telemetry.
- **Lifecycle meaning:** Process start (lifecycle may be start).
- **Usage:** `supported_but_not_currently_emitted`
- **Transmission operational:** no
- **Required fields:** `client_name`, `event_type`, `runtime_policy_version`, `schema_version`
- **Optional fields:** `ai_used`, `arch_family`, `cli_version`, `duration_bucket`, `enabled_assessment_heads`, `failure_category`, `lifecycle`, `offline_mode`, `operation_category`, `os_family`, `result`
- **Prohibited fields:** Any field outside the approved allowlist is rejected. Forbidden identity/path/credential field names are rejected.
- **Constraints:** Shared event shape; no additional event-specific requiredness is enforced by current validators.
- **Privacy:** Privacy projection is mandatory. Consent cannot expand fields. Transport-bound events must pass the pre-transport privacy gate. Cloud mapping is independently versioned. Default transport remains unavailable; HTTP requires explicit configuration. installation_id and wire event_id are not Engine catalog fields.

Illustrative example:

```json
{
  "client_name": "codestrata_cli",
  "event_type": "application_started",
  "runtime_policy_version": "1.0",
  "schema_version": "1.0"
}
```

### `feature_completed`

- **Purpose:** Records that a categorical feature or command operation completed.
- **Lifecycle meaning:** Feature/operation completion.
- **Usage:** `emitted_by_current_runtime`
- **Transmission operational:** no
- **Required fields:** `client_name`, `event_type`, `runtime_policy_version`, `schema_version`
- **Optional fields:** `ai_used`, `arch_family`, `cli_version`, `duration_bucket`, `enabled_assessment_heads`, `failure_category`, `lifecycle`, `offline_mode`, `operation_category`, `os_family`, `result`
- **Prohibited fields:** Any field outside the approved allowlist is rejected. Forbidden identity/path/credential field names are rejected.
- **Constraints:** Shared event shape; no additional event-specific requiredness is enforced by current validators.
- **Privacy:** Privacy projection is mandatory. Consent cannot expand fields. Transport-bound events must pass the pre-transport privacy gate. Cloud mapping is independently versioned. Default transport remains unavailable; HTTP requires explicit configuration. installation_id and wire event_id are not Engine catalog fields.

Illustrative example:

```json
{
  "ai_used": false,
  "client_name": "codestrata_cli",
  "duration_bucket": "s_1_10",
  "event_type": "feature_completed",
  "lifecycle": "complete",
  "operation_category": "assess",
  "result": "success",
  "runtime_policy_version": "1.0",
  "schema_version": "1.0"
}
```

### `feature_invoked`

- **Purpose:** Records that a categorical feature or command operation began.
- **Lifecycle meaning:** Feature/operation start.
- **Usage:** `emitted_by_current_runtime`
- **Transmission operational:** no
- **Required fields:** `client_name`, `event_type`, `runtime_policy_version`, `schema_version`
- **Optional fields:** `ai_used`, `arch_family`, `cli_version`, `duration_bucket`, `enabled_assessment_heads`, `failure_category`, `lifecycle`, `offline_mode`, `operation_category`, `os_family`, `result`
- **Prohibited fields:** Any field outside the approved allowlist is rejected. Forbidden identity/path/credential field names are rejected.
- **Constraints:** Shared event shape; no additional event-specific requiredness is enforced by current validators.
- **Privacy:** Privacy projection is mandatory. Consent cannot expand fields. Transport-bound events must pass the pre-transport privacy gate. Cloud mapping is independently versioned. Default transport remains unavailable; HTTP requires explicit configuration. installation_id and wire event_id are not Engine catalog fields.

Illustrative example:

```json
{
  "ai_used": false,
  "client_name": "codestrata_cli",
  "event_type": "feature_invoked",
  "lifecycle": "start",
  "operation_category": "assess",
  "runtime_policy_version": "1.0",
  "schema_version": "1.0"
}
```

### `operation_failed`

- **Purpose:** Records that a categorical operation failed with a bounded failure category.
- **Lifecycle meaning:** Feature/operation failure.
- **Usage:** `emitted_by_current_runtime`
- **Transmission operational:** no
- **Required fields:** `client_name`, `event_type`, `runtime_policy_version`, `schema_version`
- **Optional fields:** `ai_used`, `arch_family`, `cli_version`, `duration_bucket`, `enabled_assessment_heads`, `failure_category`, `lifecycle`, `offline_mode`, `operation_category`, `os_family`, `result`
- **Prohibited fields:** Any field outside the approved allowlist is rejected. Forbidden identity/path/credential field names are rejected.
- **Constraints:** Shared event shape; no additional event-specific requiredness is enforced by current validators.
- **Privacy:** Privacy projection is mandatory. Consent cannot expand fields. Transport-bound events must pass the pre-transport privacy gate. Cloud mapping is independently versioned. Default transport remains unavailable; HTTP requires explicit configuration. installation_id and wire event_id are not Engine catalog fields.

Illustrative example:

```json
{
  "client_name": "codestrata_cli",
  "event_type": "operation_failed",
  "failure_category": "unavailable",
  "lifecycle": "fail",
  "operation_category": "assess",
  "result": "failure",
  "runtime_policy_version": "1.0",
  "schema_version": "1.0"
}
```

## Shared fields

### `ai_used`

- **Type:** `boolean`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** none
- **Max length:** n/a
- **Privacy classification:** `boolean`
- **Source:** `command_runtime_categorical_context`
- **Normalization:** boolean only; no model IDs or token counts
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `False`

### `arch_family`

- **Type:** `enum`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** `arch_family`
- **Max length:** n/a
- **Privacy classification:** `low_cardinality_category`
- **Source:** `architecture_category`
- **Normalization:** exact enum value
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `arm64`

### `cli_version`

- **Type:** `string`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** none
- **Max length:** 32
- **Privacy classification:** `bounded_version`
- **Source:** `cli_package_metadata`
- **Normalization:** trimmed; path markers rejected; max 32 chars
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `0.2.0`
- **Notes:** Package version string when supplied.

### `client_name`

- **Type:** `string`
- **Requiredness:** `required`
- **Omitted when unavailable:** no
- **Enum:** none
- **Max length:** 64
- **Privacy classification:** `public_constant`
- **Source:** `runtime_constant`
- **Normalization:** must equal codestrata_cli
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `codestrata_cli`
- **Notes:** Only codestrata_cli is accepted in the current runtime.

### `duration_bucket`

- **Type:** `enum`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** `duration_bucket`
- **Max length:** n/a
- **Privacy classification:** `coarse_bucket`
- **Source:** `privacy_safe_derived_bucket`
- **Normalization:** exact named category only; no exact duration retained
- **Bucketed:** yes
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `s_1_10`
- **Notes:** Runtime accepts only named categories. Exact durations are not collected by the privacy-first event model.

### `enabled_assessment_heads`

- **Type:** `array[string]`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** none
- **Max length:** 32
- **Privacy classification:** `bounded_set_of_categories`
- **Source:** `assessment_configuration_category`
- **Normalization:** sorted unique strings; path markers rejected; max 32 chars each
- **Bucketed:** no
- **Set ordering normalized:** yes
- **Transmitted currently:** no
- **Example:** `['architecture', 'security']`
- **Notes:** Omitted when empty. Bounded strings (max 32 chars; path markers rejected). There is no closed assessment-head enum in the runtime; examples are illustrative categorical names only.

### `event_type`

- **Type:** `enum`
- **Requiredness:** `required`
- **Omitted when unavailable:** no
- **Enum:** `event_type`
- **Max length:** n/a
- **Privacy classification:** `low_cardinality_category`
- **Source:** `command_runtime_categorical_context`
- **Normalization:** exact enum value
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `feature_invoked`
- **Notes:** Required on every privacy-safe projected event.

### `failure_category`

- **Type:** `enum`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** `failure_category`
- **Max length:** n/a
- **Privacy classification:** `low_cardinality_category`
- **Source:** `primary_operation_result`
- **Normalization:** exact enum value
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `unavailable`
- **Notes:** Shared optional field. Current validators do not require it only for operation_failed or forbid it on success.

### `lifecycle`

- **Type:** `enum`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** `lifecycle`
- **Max length:** n/a
- **Privacy classification:** `low_cardinality_category`
- **Source:** `command_runtime_categorical_context`
- **Normalization:** exact enum value
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `start`
- **Notes:** Shared optional field; not event-enforced by validators today.

### `offline_mode`

- **Type:** `boolean`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** none
- **Max length:** n/a
- **Privacy classification:** `boolean`
- **Source:** `command_runtime_categorical_context`
- **Normalization:** boolean only
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `True`

### `operation_category`

- **Type:** `enum`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** `operation_category`
- **Max length:** n/a
- **Privacy classification:** `low_cardinality_category`
- **Source:** `command_runtime_categorical_context`
- **Normalization:** exact enum value
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `assess`

### `os_family`

- **Type:** `enum`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** `os_family`
- **Max length:** n/a
- **Privacy classification:** `low_cardinality_category`
- **Source:** `operating_system_category`
- **Normalization:** exact enum value
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `macos`

### `result`

- **Type:** `enum`
- **Requiredness:** `optional`
- **Omitted when unavailable:** yes
- **Enum:** `result`
- **Max length:** n/a
- **Privacy classification:** `low_cardinality_category`
- **Source:** `primary_operation_result`
- **Normalization:** exact enum value
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `success`
- **Notes:** Shared optional field across the common event shape.

### `runtime_policy_version`

- **Type:** `string`
- **Requiredness:** `required`
- **Omitted when unavailable:** no
- **Enum:** none
- **Max length:** n/a
- **Privacy classification:** `public_constant`
- **Source:** `runtime_constant`
- **Normalization:** injected by projection from runtime policy
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `1.0`
- **Notes:** Always added by privacy projection.

### `schema_version`

- **Type:** `string`
- **Requiredness:** `required`
- **Omitted when unavailable:** no
- **Enum:** none
- **Max length:** n/a
- **Privacy classification:** `public_constant`
- **Source:** `runtime_constant`
- **Normalization:** injected by projection as runtime event schema version
- **Bucketed:** no
- **Set ordering normalized:** no
- **Transmitted currently:** no
- **Example:** `1.0`
- **Notes:** Always added by privacy projection.

## Enums

### `arch_family`

Unknown values: `rejected`.

- `arm64` — 64-bit ARM architecture.
- `other` — Other or unclassified architecture.
- `x86_64` — 64-bit x86 architecture.

### `duration_bucket`

Unknown values: `rejected`.
Duration buckets are named categories only; exact duration is not retained.

- `gt_5m` — Coarse duration category greater than about 5m.
- `lt_1s` — Coarse duration category under one second.
- `m_1_5` — Coarse duration category from about 1m to 5m.
- `s_10_60` — Coarse duration category from about 10s to 60s.
- `s_1_10` — Coarse duration category from about 1s to 10s.

### `event_type`

Unknown values: `rejected`.

- `application_completed` — CLI application/process completed.
- `application_started` — CLI application/process started.
- `feature_completed` — A feature or command path completed.
- `feature_invoked` — A feature or command path was invoked.
- `operation_failed` — An operation failed.

### `failure_category`

Unknown values: `rejected`.

- `internal` — Internal error category.
- `timeout` — Timeout failure.
- `unavailable` — Dependency or capability unavailable.
- `unknown` — Unclassified failure.
- `validation` — Validation failure.

### `lifecycle`

Unknown values: `rejected`.

- `complete` — Successful/terminal completion.
- `fail` — Failure terminal state.
- `start` — Start of an operation or process.

### `operation_category`

Unknown values: `rejected`.

- `assess` — Assessment-related operation.
- `other` — Other categorical operation.
- `report` — Report-related operation.

### `os_family`

Unknown values: `rejected`.

- `linux` — Linux family operating system.
- `macos` — macOS family operating system.
- `other` — Other or unclassified OS family.
- `windows` — Windows family operating system.

### `result`

Unknown values: `rejected`.

- `cancelled` — Operation cancelled.
- `failure` — Operation failed.
- `success` — Operation succeeded.
- `unknown` — Result not classified.

## Cross-field rules

- **`client_name_fixed`:** client_name must equal codestrata_cli; other clients are rejected.
- **`consent_cannot_expand_fields`:** Session consent cannot expand the approved field set or bypass projection.
- **`empty_heads_omitted`:** enabled_assessment_heads is omitted from intake when empty.
- **`projection_injects_versions`:** Privacy projection always injects schema_version and runtime_policy_version onto the privacy-safe payload.
- **`shared_event_shape`:** The current privacy-first runtime applies one shared typed event shape to all event types. Event-specific requiredness beyond event_type and client_name is not enforced by validators today.
- **`unknown_enum_rejected`:** Unknown enum values are rejected (no silent forward compatibility).

## Never collected

- **`account_identifiers`** — Account identifiers are never collected.
- **`ai_responses`** — AI responses are never collected.
- **`api_keys`** — API keys are never collected.
- **`argv`** — Raw argv is never collected.
- **`authorization_headers`** — Authorization headers are never collected.
- **`command_line`** — Full command lines are never collected.
- **`cookies`** — Cookies are never collected.
- **`credentials`** — Credentials are never collected.
- **`customer_identifiers`** — Customer identifiers are never collected.
- **`cwd`** — Current working directory is never collected.
- **`email_addresses`** — Email addresses are never collected.
- **`endpoint_urls`** — Endpoint URLs are never collected as event fields.
- **`environment_variable_values`** — Environment-variable values are never collected.
- **`evidence`** — Evidence objects are never collected.
- **`exact_cost`** — Exact cost values are never collected.
- **`exact_model_ids`** — Exact model IDs are never collected.
- **`exact_token_counts`** — Exact token counts are never collected.
- **`exception_messages`** — Exception messages are never collected.
- **`file_paths`** — File paths are never collected.
- **`findings`** — Assessment Findings are never collected.
- **`hostnames`** — Hostnames are never collected.
- **`installation_identity`** — Installation identity is not used by the privacy-first runtime.
- **`ip_addresses`** — IP addresses are never collected.
- **`organization_names`** — Organization names are never collected.
- **`output_paths`** — Output directory paths are never collected.
- **`package_names`** — Package names are never collected by the privacy-first runtime.
- **`project_names`** — Project names are never collected.
- **`prompts`** — AI prompts are never collected.
- **`queue_contents`** — Queue contents are never collected as event fields.
- **`recommendations`** — Recommendations are never collected.
- **`report_paths`** — Report paths are never collected.
- **`repository_names`** — Repository names are never collected.
- **`repository_urls`** — Repository URLs are never collected.
- **`secrets`** — Secrets are never collected.
- **`source_code`** — Source code is never collected.
- **`stack_traces`** — Stack traces are never collected.
- **`usernames`** — Usernames are never collected.

## Validation and rejection

- `consent_does_not_bypass_validation`
- `enum_values_bounded`
- `extra_fields_forbidden`
- `forbidden_field_names_rejected`
- `invalid_combinations_rejected_where_modeled`
- `path_like_values_rejected_where_applicable`
- `secret_like_values_rejected_where_applicable`
- `unknown_fields_rejected`
- `unsafe_value_shapes_rejected`
- `values_not_echoed_in_errors`

## Bounds

- Max event size (bytes): `4096`
- Max property count: `24`
- Max string length: `64`

## Change policy

Changes to event names, field names, types, requiredness, enums,
privacy classifications, never-collected categories, or cross-field
rules require:

- `catalog_artifact_update_required`
- `code_change_required`
- `privacy_review_required`
- `runtime_event_schema_remains_1_0_unless_serialized_event_changes`
- `schema_or_policy_version_review_required`
- `tests_required`

## Limitations

- `cloud_mapping_independently_versioned`
- `community_cloud_contracts_separate`
- `consent_cannot_expand_fields`
- `derived_from_typed_runtime_models`
- `extension_clients_deferred`
- `http_transport_requires_explicit_configuration`
- `installation_identity_not_used`
- `legacy_events_excluded`
- `pre_transport_privacy_gate_required`
- `preview_command_available`
- `runtime_event_schema_remains_1_0`
- `transmission_not_operational`

## Related

- [telemetry-transport.md](telemetry-transport.md)
- [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md)
- [telemetry-preview.md](telemetry-preview.md)
- [telemetry-status.md](telemetry-status.md)
- [telemetry-runtime.md](telemetry-runtime.md)
- [telemetry.md](telemetry.md)
- [../PRIVACY.md](../PRIVACY.md)
