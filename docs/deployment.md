# Deployment

Production is a single server running Docker Compose (`deploy/docker-compose.yml`):

| Service | What |
|---|---|
| `db` | PostgreSQL 17 |
| `api` | FastAPI (built from `api/Dockerfile`), uploads on a volume |
| `web` | Caddy with automatic HTTPS. Serves the landing page at `/`, the app at `/app/` and these docs at `/docs/`, and proxies `/api` and `/files` to the API |

## Provisioning and deploys (Ansible)

`deploy/ansible/site.yml` takes a fresh Ubuntu server to a running Chalkback, and the same
playbook deploys every new version. It runs in a container, so it works the same from Windows,
macOS and Linux. See `deploy/ansible/README.md` for the details.

| Role | What it does |
| --- | --- |
| `base` | Package upgrades, unattended security upgrades, fail2ban, a swap file |
| `ssh` | Keys only: no password logins, root only with a key |
| `firewall` | ufw: SSH, HTTP and HTTPS only |
| `docker` | Docker Engine and Compose from Docker's repository; a `deploy` user |
| `app` | Ships `main` with `git archive` (tracked files only), generates secrets on the server, builds and starts the stack, waits for HTTPS health |

### First deploy

1. **Server.** Any Ubuntu server you can reach as root with an SSH key (a Hetzner CX22 is
   plenty). Connect once with plain `ssh` so its host key is in your `known_hosts`.
2. **Inventory.** Copy `deploy/ansible/inventory.example.ini` to `inventory.ini` (gitignored) and
   set the server address and `chalkback_domain`. Before a real domain is pointed at the server,
   `<ip-with-dashes>.sslip.io` resolves to it and gets a real certificate.
3. **Run** `deploy/ansible/run.sh`. Caddy fetches the certificate on the first request.

Later deploys: `deploy/ansible/run.sh --tags app`.

### Secrets

`POSTGRES_PASSWORD` and `JWT_SECRET` are generated on the server on the first run, in
`/opt/chalkback/secrets/generated.env` (root only), and never leave it. Integrations go in
`/opt/chalkback/secrets/extra.env` by hand: `ANTHROPIC_API_KEY`, `RESEND_API_KEY`,
`EMAIL_FROM`, `TELEGRAM_BOT_TOKEN`, `VITE_TLDRAW_LICENSE_KEY`. Without an Anthropic key the app
runs in mock-AI mode and spends nothing.

### Continuous deployment

`.github/workflows/deploy.yml` runs the playbook's `app` role after **CI** succeeds on `main`.
It needs the repository secrets `DEPLOY_HOST` and `DEPLOY_SSH_KEY` (a key the server accepts for
root) and stays off until you set the repository **variable** `DEPLOY_ENABLED=true`.

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
cd /opt/chalkback/current/deploy
docker compose -p chalkback ps
docker compose -p chalkback logs -f api
docker compose -p chalkback exec db pg_dump -U chalkback chalkback > backup.sql   # database backup
```

Releases are unpacked in `/opt/chalkback/releases/<commit>`, `current` points at the running
one, and the last three are kept.

Uploaded board images live in the `uploads` volume. Back it up together with the database.
