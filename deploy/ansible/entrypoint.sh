#!/bin/sh
# Files mounted from Windows look world-writable: ssh refuses such keys and Ansible ignores
# such an ansible.cfg, so use private copies of both.
set -e
install -d -m 700 /root/.ssh
install -m 600 /ssh/key /root/.ssh/id_ed25519
[ -f /ssh/known_hosts ] && install -m 600 /ssh/known_hosts /root/.ssh/known_hosts
install -D -m 644 ansible.cfg /etc/ansible/ansible.cfg
export ANSIBLE_CONFIG=/etc/ansible/ansible.cfg
exec ansible-playbook -i inventory.ini site.yml "$@"
