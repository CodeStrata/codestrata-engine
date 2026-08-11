# compose-managed (controlled fixture)

Docker Compose stub with managed database/cache services for Epic 4 Slice 4.13.

## Intentional positives

| Path | Signal | Notes |
|------|--------|-------|
| `docker-compose.yml` | Managed services | postgres and redis service definitions |

## Safety

- No credentials or real connection strings
- Static compose file only; do not start containers for validation
- CodeStrata-owned validation fixture
