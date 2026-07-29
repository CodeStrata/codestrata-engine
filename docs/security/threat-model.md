# Threat model (Community Edition)

**Scope:** Local CLI / optional MCP on localhost; GitHub clone; optional
Bedrock/OpenAI. Hosted multi-tenant Platform isolation is out of scope.

## Assets

* Operator workstation credentials (GitHub tokens, cloud keys, DB URLs)
* Analyzed repository contents (may include secrets)
* Generated reports and knowledge-store artifacts
* Process integrity of the CodeStrata runtime

## Trust boundaries

```text
[Untrusted repo / GitHub] --clone/read--> [CodeStrata Engine]
[Operator config / env]  --load-------> [CodeStrata Engine]
[CodeStrata Engine]      --optional--> [Cloud AI / MCP client]
[CodeStrata Engine]      --write-----> [Output reports dir]
```

## Adversaries

| Adversary | Goal |
| --------- | ---- |
| Malicious repository | Escape sandbox, RCE, exfiltrate operator secrets |
| Local attacker (shared host) | Read tokens from env/tmp, DoS via large trees |
| Compromised dependency | Supply-chain execution |
| Misconfigured operator | Accidental credential leakage into reports/logs |

## Key threats and mitigations

| Threat | Mitigation |
| ------ | ---------- |
| Command injection via repo URL/path | `shell=False`; argv lists; URL parsing |
| Path traversal / symlink escape | `os.walk(followlinks=False)`; resolve+`relative_to`; refuse symlink reads |
| Code execution from target repo | Never import/exec target modules; text/byte reads only |
| Unsafe deserialization | No pickle; `yaml.safe_load` only |
| Secret leakage in reports/logs | Redactors; `token_env`; effective-config scrubbing |
| Unbounded resource use | `max_source_files`, char limits, timeouts, MCP result caps |
| Enterprise / Platform bleed into CE | Export excludes Enterprise KG runtime; lazy CLI stubs |
| AI provider abuse | `--no-ai` default; profiles gate external LLM |
| Malicious third-party extension package | Entry points run in-process; analyzer extensions require `[extensions.analyzers].enabled` allowlist; reserved namespaces documented |

## Out of scope (current CE)

* Multi-tenant hosted control plane isolation
* Browser XSS in HTML reports opened from untrusted origins (reports are local files)
* Guaranteeing zero false negatives in secret detection of target repos

## Residual risks

* Pattern-based report redaction is heuristic; novel secret formats may still
  appear in source excerpts. Paths/line references are preserved.
* Absolute output paths chosen by the operator are trusted
* Optional extras (`bedrock`, `openai`, `mcp`, `pgvector`) expand the attack surface when installed
* Extension entry points execute with CLI privileges; only enable packages you trust
* Hosted multi-tenant isolation still out of CE scope

## Hardening checklist

Use before a Community release candidate or production-like local deployment.

### Defaults

- [ ] Profile `community` (or `local`) — Enterprise KG disabled
- [ ] Assess runs with `--no-ai` unless AI is intentionally required
- [ ] MCP disabled unless explicitly enabled; bind `127.0.0.1`
- [ ] Knowledge store / projection disabled unless needed
- [ ] `token_env` used for GitHub auth (no embedded tokens)

### Runtime bounds

- [ ] `analysis.runtime.max_source_files` appropriate for target repos
- [ ] `analysis.runtime.max_source_chars` / workers reviewed
- [ ] Provider timeouts configured (Bedrock/OpenAI/PMD/git)

### Supply chain

- [ ] `pip-audit` clean for runtime dependencies (ignore or upgrade known
      dev-only issues)
- [ ] Optional extras reviewed separately (`bedrock`, `openai`, `mcp`,
      `pgvector`)
- [ ] Prefer `python scripts/verify_release.py` / `codestrata release check`
      for the full maintainer gate

### Community surface

- [ ] Public export validation passes
- [ ] Platform and Enterprise-only packages are absent from the Community
      Engine distribution
- [ ] Extension hook `codestrata.extensions` present when shipping extensions

### Verification

- [ ] `ruff check .`
- [ ] `mypy src` (or project-equivalent)
- [ ] `pytest`
- [ ] Fresh Engine install + assess smoke
