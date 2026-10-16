#!/usr/bin/env bash
# One-time setup of a fresh Hetzner Ubuntu 24.04 server for Chalkback.
# Run as root:  bash bootstrap-server.sh <repo-url> "<ssh public key for the deploy user>"
set -euo pipefail

REPO_URL="${1:?usage: bootstrap-server.sh <repo-url> <deploy-ssh-pubkey>}"
DEPLOY_KEY="${2:?usage: bootstrap-server.sh <repo-url> <deploy-ssh-pubkey>}"
APP_DIR=/opt/chalkback

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get -y install ca-certificates curl git ufw fail2ban unattended-upgrades

# Docker Engine + Compose plugin (official repository)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Deploy user (used by CI over SSH), allowed to run docker
id deploy &>/dev/null || adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
grep -qxF "$DEPLOY_KEY" /home/deploy/.ssh/authorized_keys 2>/dev/null \
  || echo "$DEPLOY_KEY" >> /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

# Firewall: SSH + HTTP(S) only
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

# SSH: keys only
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload ssh

systemctl enable --now fail2ban unattended-upgrades

# Application checkout
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
chown -R deploy:deploy "$APP_DIR"

echo
echo "Done. Next: create $APP_DIR/deploy/.env from deploy/.env.example, then run"
echo "  sudo -u deploy $APP_DIR/deploy/deploy.sh"
