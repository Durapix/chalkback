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

Production is <https://chalkback.xyz>. Its DNS is on Cloudflare with the proxy on. Cloudflare
passes plain HTTP to the server, so Caddy gets its Let's Encrypt certificate with the HTTP
challenge. The server has a valid certificate, so Cloudflare's SSL mode can be **Full (strict)**.
Caddy already redirects HTTP to HTTPS. If a certificate renewal ever fails, check that Cloudflare
still lets `/.well-known/acme-challenge/` through on plain HTTP.

Later deploys: `deploy/ansible/run.sh --tags app`.

### Secrets

`POSTGRES_PASSWORD` and `JWT_SECRET` are generated on the server on the first run, in
`/opt/chalkback/secrets/generated.env` (root only), and never leave it. Integrations go in
`/opt/chalkback/secrets/extra.env` by hand: `ANTHROPIC_API_KEY`, `RESEND_API_KEY`,
`EMAIL_FROM`, `TELEGRAM_BOT_TOKEN`, `VITE_TLDRAW_LICENSE_KEY`. Without an Anthropic key the app
runs in mock-AI mode and spends nothing.

After changing `extra.env`, run `deploy/ansible/run.sh --tags app`. The tldraw key is built into
the web app, so it only takes effect after that rebuild, and browsers may need a hard refresh.
Without a valid key, tldraw hides the board editor after about 5 seconds on any HTTPS domain.

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

### Accounts

Registration is closed in production. Create real teacher accounts on the server. Commands that
change an address ask for confirmation first, and passwords are typed at a prompt (twice), never
given as arguments. From your machine, wrap each one in `ssh -t <server> '…'`:

```bash
docker exec -it chalkback-api-1 python -m app.cli list-teachers
docker exec -it chalkback-api-1 python -m app.cli create-teacher --email you@example.com --name "Your Name"
docker exec -it chalkback-api-1 python -m app.cli set-email --email typo@exmaple.com --new-email you@example.com
docker exec -it chalkback-api-1 python -m app.cli set-password --email you@example.com
docker exec -it chalkback-api-1 python -m app.cli delete-teacher --email typo@exmaple.com
```

To check that e-mail works after configuring Resend, send a sample reminder (in Serbian, made
with the real templates; nothing is stored):

```bash
docker exec -it chalkback-api-1 python -m app.cli send-test-email --to you@example.com
```

To check notifications, have the student turn them on, then send them a sample:

```bash
docker exec -it chalkback-api-1 python -m app.cli send-test-push --email student@example.com
```

A mistyped address is fixed with `set-email`, which keeps the account and its data. `delete-teacher`
only removes accounts that have no students or lessons yet.

Reminders for students of the public demo teacher are logged as `skipped` and never delivered.
Only students of real teacher accounts get e-mail and Telegram reminders.

### Backups

A systemd timer (Ansible role `backup`) runs `/usr/local/bin/chalkback-backup` every night at
03:30 UTC. It writes a `pg_dump` and an archive of the uploads volume (board images and draw.io
sources) to `/opt/chalkback/backups`, and keeps 14 days of them. Run it any time with
`systemctl start chalkback-backup`.

These backups live on the same server, so they protect against mistakes and bad deploys, not
against losing the server. For that, copy the folder elsewhere now and then, or turn on the
hosting provider's snapshots.

Restore:

```bash
cd /opt/chalkback/backups
docker exec -i chalkback-db-1 pg_restore -U chalkback -d chalkback --clean --if-exists < db-<stamp>.dump
docker exec -i chalkback-api-1 tar xzf - -C /data < uploads-<stamp>.tar.gz
```
