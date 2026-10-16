# Deployment

Production is a single Hetzner server running Docker Compose (`deploy/docker-compose.yml`):

| Service | What |
|---|---|
| `db` | PostgreSQL 17 |
| `api` | FastAPI (built from `api/Dockerfile`), uploads on a volume |
| `web` | Caddy with automatic HTTPS. Serves the landing page at `/`, the app at `/app/` and these docs at `/docs/`, and proxies `/api` and `/files` to the API |

## First deploy

1. **Server.** Create a Hetzner Cloud server (Ubuntu 24.04; a CX22 is plenty) with your SSH key.
2. **DNS.** Point an `A` (and `AAAA`) record for your domain at the server.
3. **Bootstrap** (as root, once). This installs Docker, a firewall (22/80/443), fail2ban and
   unattended upgrades, disables SSH password login, creates a `deploy` user and clones the repo
   to `/opt/chalkback`:

    ```bash
    curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/deploy/bootstrap-server.sh \
      | bash -s -- https://github.com/<owner>/<repo>.git "ssh-ed25519 AAAA… deploy@ci"
    ```

4. **Secrets.** As `deploy`, copy `deploy/.env.example` to `deploy/.env` and fill it in.
   Generate `POSTGRES_PASSWORD` and `JWT_SECRET` with `openssl rand -hex 32`.
5. **Start.** Run `/opt/chalkback/deploy/deploy.sh`. Caddy fetches certificates on the first
   request.

## Continuous deployment

`.github/workflows/deploy.yml` runs after **CI** succeeds on `main`. It SSHes in as `deploy` and
runs `deploy/deploy.sh`, which fast-forwards `main`, rebuilds and restarts the stack, and waits
for `/api/health`.

Repository secrets: `DEPLOY_HOST`, `DEPLOY_SSH_KEY` (the private key matching the public key given
to `bootstrap-server.sh`), and `ANTHROPIC_API_KEY` for AI reviews. Deploys stay off until you set
the repository **variable** `DEPLOY_ENABLED=true`.

## Running the production stack locally

The same images run on your machine over plain HTTP, using `deploy/local.env` (local-only values):

```bash
cd deploy
docker compose --env-file local.env up -d --build
```

Open <http://localhost:8080> (landing), <http://localhost:8080/app/> (app) and
<http://localhost:8080/docs/>. Stop with `docker compose --env-file local.env down`; add `-v` to
also wipe the database and uploads.

`SITE_ADDRESS`, `PUBLIC_URL`, `HTTP_PORT` and `HTTPS_PORT` are what make this work. In production
they default to the bare `DOMAIN`, `https://DOMAIN`, 80 and 443.

## Operations

```bash
cd /opt/chalkback/deploy
docker compose ps
docker compose logs -f api
docker compose exec db pg_dump -U chalkback chalkback > backup.sql   # database backup
```

Uploaded board images live in the `uploads` volume. Back it up together with the database.
