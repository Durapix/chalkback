# Chalkback

**Your whiteboard remembers, so your students do too.**

Chalkback is a learning platform for tutors. You upload photos, screenshots or PDF exports of the
whiteboards from your lessons. Chalkback then:

1. **Rebuilds each board** as a live [tldraw](https://tldraw.dev) whiteboard. Handwriting becomes
   text, formulas become editable LaTeX, and boxes, arrows and graphs become real shapes. The
   original photo stays underneath as a locked, fadeable layer.
2. **Writes a recap** of the lesson for the student: topics, key points, formulas, exercises and
   what to practise next, in the student's language.
3. **Reminds the student** on Telegram or by email before their next lesson.

Teachers manage students and lessons. Students log in to see their own lessons, reopen the boards
and keep working on them.

!!! info "Built on autopilot"
    The whole project was written, reviewed, merged, released, documented and deployed by an AI
    coding agent. See [Built on autopilot](autopilot.md).

## At a glance

| | |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (SQLite in dev, PostgreSQL in production) |
| AI | Claude vision and structured outputs, through the official `anthropic` SDK; draw.io boards need no AI |
| Frontend | React 19, Vite, TypeScript, tldraw, KaTeX |
| Reminders | Resend email, Telegram Bot API, Web Push notifications |
| Hosting | Docker Compose and Caddy on a Hetzner server |

Next: [Getting started](getting-started.md).
