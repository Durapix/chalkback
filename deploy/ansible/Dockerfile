# Ansible control node in a container (Ansible does not run natively on Windows).
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client git \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "ansible>=11,<13" \
 && git config --system --add safe.directory '*'
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
WORKDIR /repo/deploy/ansible
ENTRYPOINT ["sh", "/usr/local/bin/entrypoint.sh"]
