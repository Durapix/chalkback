#!/usr/bin/env bash
# Run the playbook from a container. Extra arguments go to ansible-playbook.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
key="${SSH_KEY:-$HOME/.ssh/chalkback}"
[ -f "$here/inventory.ini" ] || { echo "Create $here/inventory.ini from inventory.example.ini" >&2; exit 1; }
[ -f "$key" ] && [ -f "$key.pub" ] || { echo "SSH key $key(.pub) not found (set SSH_KEY)" >&2; exit 1; }

docker info >/dev/null 2>&1 || { echo "Docker is not running (start Docker Desktop and try again)" >&2; exit 1; }

# Git Bash on Windows: hand Docker Windows paths and stop MSYS rewriting container paths.
winpath() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else echo "$1"; fi; }
export MSYS_NO_PATHCONV=1

docker build -q -t chalkback-ansible "$(winpath "$here")" >/dev/null
tty=(); [ -t 1 ] && tty=(-t)  # colors in a terminal; CI has no TTY
docker run --rm "${tty[@]}" \
  -v "$(winpath "$repo"):/repo:ro" \
  -v "$(winpath "$key"):/ssh/key:ro" \
  -v "$(winpath "$key.pub"):/ssh/key.pub:ro" \
  -v "$(winpath "$HOME/.ssh/known_hosts"):/ssh/known_hosts:ro" \
  chalkback-ansible "$@"
