# Edge container: builds the React app and the docs, then serves them, the landing page
# and the API proxy with Caddy (automatic HTTPS). Build context: repository root.

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG VITE_TLDRAW_LICENSE_KEY=""
ENV VITE_BASE=/app/ VITE_TLDRAW_LICENSE_KEY=$VITE_TLDRAW_LICENSE_KEY
RUN npm run build

FROM python:3.12-slim AS docs
WORKDIR /src
COPY docs/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY mkdocs.yml ./
COPY docs/ ./docs/
RUN mkdocs build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY landing/ /srv/landing/
COPY --from=web /web/dist/ /srv/app/
COPY --from=docs /src/site/ /srv/docs/
