# Repository onboarding

Single-command workflow that takes a repository from source to a queryable
CodeStrata knowledge base by **orchestrating existing services**.

## Command

```bash
codestrata onboard <repository> \
  --config codestrata.toml \
  --output reports \
  [--force-reindex] \
  [--skip-report] \
  [--skip-index] \
  [--provider deterministic|bedrock|openai] \
  [--verbose]
```

## Workflow

1. Validate repository, config, output directory, and embedding provider
2. Enable knowledge projection/chunking/embedding/indexing (unless `--skip-index`)
3. Enable roadmap report section for initiative counts
4. Call `AssessmentApplicationService.run` (scan → assess → findings →
   recommendations → reports → knowledge)
5. Persist `repository-onboarding.json` under the assessment run directory
6. Print a leadership-friendly summary

## Manifest

`repository-onboarding.json` (schema `repository-onboarding-manifest` 1.0.0)
includes repository id, scan id, assessment/report versions, embedding
provider/model, index fingerprint, languages/frameworks, timestamps, CodeStrata
version, and counts for findings, recommendations, roadmap initiatives, and
indexed chunks.

## Notes

- Does not reimplement scanning, rules, indexing, retrieval, reporting, or
  roadmap generation.
- `--skip-report` still runs assessment/knowledge; HTML/JSON files are not written.
- `--force-reindex` clears the repository vector-store scope before indexing.

## Community vs Platform

Local onboarding and knowledge-store indexing are Community Engine capabilities.
Organizational RAG, portfolio retrieval, and hosted answering are **Platform**
capabilities. See [community-vs-platform.md](community-vs-platform.md) and
[mcp-server.md](mcp-server.md).

## Related

- [knowledge-store.md](knowledge-store.md)
- [installation.md](installation.md)
- [cli-reference.md](cli-reference.md)
