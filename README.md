# Chalkback

**Your whiteboard remembers, so your students do too.**

Chalkback turns screenshots and PDF exports of tutoring whiteboards into live, editable
[tldraw](https://tldraw.dev) boards, then uses an AI agent to summarize every lesson and
remind each student what was covered — by email, on Telegram, or as a phone notification.

**Live:** <https://chalkback.xyz> · app at [/app](https://chalkback.xyz/app/) · docs at [/docs](https://chalkback.xyz/docs/)

> This project is also an experiment: it is built, reviewed, released, documented and
> deployed by an AI coding agent running on autopilot.

## How it works

1. **Upload** a screenshot or PDF export of a past whiteboard.
2. **Reconstruct** — Claude (vision) reads the board and returns a structured scene
   (text, LaTeX formulas, shapes, arrows, coordinates). The original image stays as a locked
   background layer; the extracted elements become real, editable tldraw shapes on top.
3. **Summarize** — each lesson gets a short recap: topics, key formulas, exercises.
4. **Remind** — students get a "here's what we did last time" message before the next lesson.

## Repository layout

| Path | What |
|---|---|
| `api/` | Python FastAPI backend (lessons, boards, AI pipeline, reminders) |
| `web/` | React + Vite + TypeScript + tldraw app |
| `landing/` | Static showcase / landing page |
| `docs/` | MkDocs Material documentation |
| `deploy/` | Docker Compose + Caddy production setup (Hetzner) |
| `.github/workflows/` | CI, release and AI review workflows |

## Quick start (local)

```bash
# backend
cd api
uv sync
uv run uvicorn app.main:app --reload

# frontend (separate terminal)
cd web
npm install
npm run dev
```

The API runs at http://localhost:8000 (docs at `/docs`), the app at http://localhost:5173.
Without an `ANTHROPIC_API_KEY` the AI pipeline runs in **mock mode** with deterministic
sample output, so everything works offline.

See [`docs/`](docs/index.md) for the full documentation.

## Privacy

The public demo uses only fictional students and synthetic boards. Real student data lives
only behind login and is never used in the showcase.
