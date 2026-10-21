# Server provisioning and deploys (Ansible)

`site.yml` takes a fresh Ubuntu server to a running Chalkback, and is safe to run again for
every deploy:

| Role | What it does |
| --- | --- |
| `base` | Package upgrades, unattended security upgrades, fail2ban, a swap file |
| `ssh` | Keys only: no password logins, root only with a key |
| `firewall` | ufw: SSH, HTTP and HTTPS only |
| `docker` | Docker Engine and the Compose plugin from Docker's repository; a `deploy` user |
| `app` | Ships the chosen git ref (`git archive`, so only tracked files), writes the env file with secrets generated on the server, builds and starts the stack, waits for HTTPS health |
| `backup` | Nightly `pg_dump` and uploads archive in `/opt/chalkback/backups`, kept 14 days |

## Run

Ansible runs in a small container, so it works the same from Windows, macOS and Linux:

```bash
cp deploy/ansible/inventory.example.ini deploy/ansible/inventory.ini   # then fill it in
deploy/ansible/run.sh                       # everything
deploy/ansible/run.sh --tags app            # just deploy the app
deploy/ansible/run.sh --check --diff        # dry run
```

`run.sh` mounts the repository read-only and the SSH key named by `SSH_KEY` (default
`~/.ssh/chalkback`) together with your `known_hosts`, so connect once with plain `ssh` first.

## Secrets

- `POSTGRES_PASSWORD` and `JWT_SECRET` are generated on the server on the first run
  (`/opt/chalkback/secrets`, root only) and never leave it.
- Paid or sending integrations (`ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `TELEGRAM_BOT_TOKEN`)
  stay empty unless you put them in `/opt/chalkback/secrets/extra.env` on the server. Without
  an Anthropic key the app runs in mock-AI mode and spends nothing.

## Domain

`chalkback_domain` in the inventory is the public host name. Until a real domain points at
the server, `<ip-with-dashes>.sslip.io` resolves to it and gets a real certificate.
