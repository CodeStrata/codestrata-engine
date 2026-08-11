# Cloud / deployment signals fixture (validation only)

Purpose-built CodeStrata validation fixture for **Cloud Readiness** signal accuracy
(Epic 4 Slice 4.8). Not a customer application. Not part of a second active repo —
this tree is already `local-cloud-signals` in the ACTIVE_VALIDATION_SET.

## Intentional positives

| Path | Family | Kind | Notes |
|------|--------|------|-------|
| `Dockerfile` | container | docker | Confirmed `FROM` |
| `docker-compose.yml` | container | docker_compose | Confirmed `services:` |
| `k8s/deployment.yaml` | orchestration | kubernetes | Confirmed `apiVersion`/`kind` |
| `.github/workflows/deploy.yml` | deployment | github_actions | Confirmed deploy-step token (`kubectl`) |

Expected SharedRules: `cloud.cloud-010`, `cloud.cloud-011`, `cloud.cloud-040`,
`cloud.cloud-060` (≥3 families), `cloud.cloud-061` (deployment assets without
AWS/Azure/GCP platform markers).

## Negative controls (must not invent)

| Path | Must not become |
|------|-----------------|
| `.github/workflows/build-only.yml` | Confirmed deployment-pipeline finding |
| `config/generic-app.yaml` | Kubernetes / managed-service / platform |
| `docs/ordinary-handler-notes.md` | Serverless (prose only) |

Ordinary words (`region`, `bucket`, `queue`, `function`) alone are not provider
or serverless evidence.

## Safety

- No real cloud credentials or account identifiers
- No production deploy targets
- Static assessment only; nothing here is meant to be deployed
- Do not run Docker, kubectl, Terraform, or provider CLIs
