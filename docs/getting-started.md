# Getting started

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- Optional: Docker, for the production-like stack

## Run locally

```bash
# API: http://localhost:8000, interactive docs at /docs
cd api
uv sync
uv run uvicorn app.main:app --reload
```

```bash
# Web app: http://localhost:5173 (proxies /api and /files to the API)
cd web
npm install
npm run dev
```

On first start the API creates its database and seeds a **fictional demo**:

| Role | Email | Password |
|---|---|---|
| Teacher | `teacher@demo.chalkback` | `demo-password` |
| Student | `mia@demo.chalkback` | `demo-password` |
| Student | `luka@demo.chalkback` | `demo-password` |

## Mock mode vs. real AI

Without `ANTHROPIC_API_KEY` the reconstruction and summary steps return deterministic sample
output, so the whole app works offline and in tests. To use Claude, put the key in `api/.env`:

```bash
cp api/.env.example api/.env
# then set ANTHROPIC_API_KEY=...
```

`GET /api/health` reports `"ai": "claude"` or `"ai": "mock"`.

## Tests and linting

```bash
cd api && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd web && npm run build
```

## Docs

```bash
uvx --with mkdocs-material mkdocs serve   # http://localhost:8000/docs/
```
