# Configuration and execution profiles

<!-- documentation-visibility: public-contract -->

CodeStrata uses named **execution profiles** to apply secure defaults without
duplicating the rest of the configuration model. Profiles only supply defaults;
they do not replace `codestrata.toml`.

**Public contract:** `codestrata.toml` keys, profile names, and documented env
overlays are compatibility-sensitive. Prefer additive changes; deprecate before
remove.

## Compatibility notes

1. Precedence is stable: CLI (`--profile`) > environment > TOML > profile defaults.
2. Prefer additive settings. Deprecate with release notes before removal.
3. Secrets never belong in TOML — store environment variable *names* only.
4. `codestrata config validate` / `effective` are the supported diagnostics.
5. Platform API keys (`CODESTRATA_PLATFORM_API_KEY`) are **not** Engine config.

## Profiles

| Profile | Intent | Secure defaults |
| ------- | ------ | --------------- |
| `community` | Community edition (default) | Local Community defaults |
| `local` | No external LLM | Deterministic providers |
| `bedrock` | AWS Bedrock providers | Assessment + knowledge via Bedrock; region required |
| `openai` | OpenAI providers | `embedding_provider` / `answer_provider` = `openai`; API key via env name |

Additional profile names may exist for Platform-oriented deployments. Advanced
portfolio capabilities are available in CodeStrata Platform; Community assess
does not require them.

## Precedence

```text
CLI (--profile)
  > environment (CODESTRATA_PROFILE and related overlays)
  > codestrata.toml (including profile = "..." or [execution].profile)
  > profile defaults
```

Related environment overlays (also env > TOML):

| Variable | Effect |
| -------- | ------ |
| `CODESTRATA_PROFILE` | Active execution profile |
| `AWS_PROFILE` | AWS session profile (resolved at use time; env > TOML) |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | AWS region (resolved at use time; env > TOML) |
| `CODESTRATA_BEDROCK_MODEL_ID` | `[ai.bedrock].model_id` |
| `CODESTRATA_OPENAI_API_KEY_ENV` | `[ai.openai].api_key_env` (name only) |

OpenAI secrets are **never** stored in TOML. Configure only the environment
variable *name* (`api_key_env = "OPENAI_API_KEY"`) and set the value in the
process environment or `.env`.

## TOML examples

```toml
# Default when omitted: community
profile = "local"

[repository]
path = "test-fixtures/sample-js-app"
```

```toml
profile = "bedrock"

[aws]
region = "us-east-1"
# Optional: prefer export AWS_PROFILE=<your-profile> on each machine
# instead of committing a developer-specific profile name.

[ai.bedrock]
model_id = "amazon.nova-lite-v1:0"
```

```toml
profile = "openai"

[ai.openai]
api_key_env = "OPENAI_API_KEY"
embedding_model = "text-embedding-3-small"
answer_model = "gpt-4o-mini"
```

Alias form (equivalent):

```toml
[execution]
profile = "community"
```

## CLI

```bash
# Active profile + source
codestrata config profile --config codestrata.toml

# Effective non-secret settings
codestrata config effective --config codestrata.toml
codestrata config show --config codestrata.toml   # alias

# Validate profile compatibility (add --strict for credential presence)
codestrata config validate --config codestrata.toml
codestrata config validate --config codestrata.toml --profile bedrock --strict

# Assess with an explicit profile
codestrata assess --config codestrata.toml --profile local --output reports
```

## Validation behavior

Hard errors (fail load / `config validate`):

* Unknown profile name
* `local` with non-deterministic knowledge providers
* `bedrock` profile without a resolvable AWS region
* `openai` profile without OpenAI embedding/answer providers or `api_key_env`

Warnings (reported, non-fatal):

* `community` with external AI providers (prefer `bedrock` / `openai` profiles)
* `--strict` Bedrock credential hints when no profile/access key is visible

`local` + `assess --with-ai` is rejected at assessment time.

## Secrets

Effective dumps and MCP health:

* Show `api_key_env` **name** and `api_key_present` boolean — never the key
* Redact database URLs / connection strings
* AWS uses the default credentials chain; only profile/region names are shown

## Backward compatibility

Existing `codestrata.toml` files without `profile` load as **`community`**,
matching prior secure defaults. Explicit TOML keys continue to override profile
defaults.

## Related

* [runtime.md](runtime.md)
* [ai-enrichment.md](ai-enrichment.md)
* [cli-reference.md](cli-reference.md)
* [troubleshooting.md](troubleshooting.md)
* [public-contracts.md](public-contracts.md)
