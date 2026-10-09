# Non-root container example (E14.2)

Local-only recipe for a standalone CodeStrata Engine wheel inside a non-root
container. This does not publish, tag, or deploy.

## Properties

- Installs the built wheel from `engine/` (no monorepo `PYTHONPATH`)
- Runs as UID/GID `10001` (`codestrata` user)
- `network_mode: none` for offline verification
- Read-only root filesystem with explicit writable `/tmp/codestrata` and `/output`
- CPU limit `1.0` and memory limit `2G` via Compose

## Verify locally

From `engine/examples/non-root-container/`:

```bash
docker compose build
docker compose run --rm codestrata --version
```

Operational limits are defined in
`engine/src/codestrata/resources/release/headless-runtime-limits-v1.yaml`.

Automated build verification (wheel, sdist, SBOM, provenance):

```bash
cd engine
python -m verification.release_build --output reports/release-build
```
