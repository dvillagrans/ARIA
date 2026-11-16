# Deployment

ARIA's backend ships as a Docker image and deploys through GitHub Actions on
every push to `main` that touches backend code, `docker-compose.prod.yml`, or
the workflow itself. Manual runs are available via `workflow_dispatch`.

> The repository ships the pipeline as a template. You must configure the
> repository variables and secrets below before it will run. The frontend has
> a `vercel.json` configuration file but no deploy pipeline in this
> repository — Vercel deploys are done manually (see
> [Frontend](#frontend-optional)).

## Pipeline

1. **Test** (every push to `main` matching the paths above): the backend test
   suite runs with `uv run pytest tests/ -v --tb=short` on Python 3.12.
2. **Build and push**: on success, the backend Docker image is built and
   pushed to GHCR with two tags — a short commit SHA and `latest`.
3. **Deploy**: the workflow opens an SSH session to the target host and:
   - writes the runtime `.env` from the `ENV_FILE` secret — the `.env` must
     contain `ARIA_IMAGE=ghcr.io/<owner>/<image>:latest` telling
     `docker-compose.prod.yml` which image to pull;
   - logs in to GHCR with the `GHCR_TOKEN` secret;
   - pulls the new image and runs `docker compose up -d --force-recreate`;
   - polls the container health check (`GET /health`) for up to 60 seconds;
   - on failure, stops the stack and restores the previous image;
   - syncs `docker-compose.prod.yml` to the deployment directory.

## Configuration

### Repository variables

| Variable | Example | Purpose |
|---|---|---|
| `GHCR_IMAGE_NAME` | `your-user/aria-backend` | Image path on GHCR |
| `DEPLOY_PATH` | `/home/deploy/aria` | Deployment directory on the target host |

### Repository secrets

| Secret | Purpose |
|---|---|
| `VPS_HOST` | Hostname or IP of the deployment target |
| `VPS_USER` | SSH user on the deployment target |
| `VPS_SSH_KEY` | Private SSH key allowed to deploy |
| `GHCR_TOKEN` | Token with read access to the GHCR image |
| `ENV_FILE` | Full contents of the runtime `.env` file |

The `GITHUB_TOKEN` used to push to GHCR is provided automatically by Actions
with `packages: write` permission.

## Runtime layout

`docker-compose.prod.yml` runs a single `fastapi` service:

- image: `${ARIA_IMAGE}` from the runtime `.env` (falls back to a locally
  built `aria-backend:local` when unset);
- environment from the `.env` file in the deployment directory;
- container-only port `8000` (exposed, not published) behind a health check;
- on the user-defined bridge network `aria_backend`, with `proxy.aliases` /
  `proxy.network` labels for a reverse proxy that understands those labels —
  remove or adapt them if you use a different proxy;
- restart policy `unless-stopped`.

## Upgrade note

`docker-compose.prod.yml` now names the bridge network `aria_backend` (it used
to rely on the Compose default, `aria_default`). A reverse proxy attached to
the old `aria_default` network must join `aria_backend` before the next deploy,
otherwise it can no longer reach `aria-fastapi`:

```bash
docker network connect aria_backend <proxy-container>
```

## Manual operations

```bash
# Check container health from the deployment directory
docker inspect --format='{{.State.Health.Status}}' aria-fastapi

# Tail logs
docker compose -f docker-compose.prod.yml logs -f fastapi

# Roll back manually
docker compose down
docker run -d --name aria-fastapi --env-file .env --network aria_backend <old-image>
```
