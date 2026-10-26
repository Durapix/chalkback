---
layout: default
title: Chalkback
---

<p align="center">
  <img src="branding/out/icon-192.png" alt="Chalkback logo" width="96" height="96">
</p>

**Your whiteboard remembers, so your students do too.**

Chalkback turns tutoring whiteboards into live, editable [tldraw](https://tldraw.dev) boards,
writes a recap of every lesson, and reminds each student what was covered before the next one —
by e-mail, on Telegram, or as a phone notification.

**[Try the live demo →](https://chalkback.xyz/app/)** · [Website](https://chalkback.xyz) ·
[Documentation](https://chalkback.xyz/docs/) · [Releases](https://github.com/Durapix/chalkback/releases) ·
[Source](https://github.com/Durapix/chalkback)

The demo login is on the sign-in page. Every student in the demo is fictional.

---

## How it works

1. **Bring the board.** Upload draw.io exports, screenshots or PDFs from past lessons. draw.io
   boards are imported exactly, with no AI and at no cost. Photos and screenshots are rebuilt by
   Claude vision.
2. **Keep working on it.** Every board becomes an editable tldraw canvas: shapes, formulas,
   tables, connectors and handwriting, ready to continue in the next lesson.
3. **Get the recap.** Each lesson gets a short summary for the student, in their language:
   topics, key points, formulas and what to practise.
4. **Remind the student.** The day before the next lesson, the recap arrives where the student
   is: e-mail, Telegram, or a notification on their phone.

## What makes it different

- **It reads boards the way a tutor does.** Flowcharts are read as algorithms (inputs, loops,
  decisions, calls, recursion), so a recap says *what the algorithm computes*, not which boxes
  it has. Entity-relationship diagrams are recognised as data models, and red and green table
  cells as rows a query ruled out or kept.
- **It is honest.** When a board is too thin to say much, the recap says so instead of inventing
  a purpose.
- **Built for real tutoring.** Serbian recaps are written in Cyrillic, section titles follow the
  recap's language, and boards stay faithful to the original — colours, tables, wires and all.
- **Reminders that cost nothing to run.** Telegram connects with a one-tap link, push
  notifications need no third-party account, and e-mail is sent from the project's own domain.
- **Careful with student data.** The public demo uses fictional students and can never send real
  messages, and server secrets are generated on the server and never leave it.

## Built on autopilot

Chalkback is also an experiment: every part of it was written, reviewed, fixed, merged, released,
documented and deployed by an AI coding agent ([Claude Code](https://claude.com/claude-code)).
The human set the goals and made the decisions; the agent did the engineering.

| | |
|---|---|
| Branches | 30+ merged, each through its own pull request, self-reviewed, with CI green before merge |
| Releases | Tagged with semantic versions; release notes come from the [changelog](https://github.com/Durapix/chalkback/blob/main/CHANGELOG.md) |
| Checks on every PR | API tests and lint, web type-check and build, strict docs build, Docker images, Ansible syntax |
| Deploys | One Ansible playbook takes a fresh server to a running, hardened production |

The landing page at [chalkback.xyz](https://chalkback.xyz/#autopilot) shows the full log,
generated from the real git history.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL |
| AI | Claude (vision and structured outputs) through the official `anthropic` SDK |
| Frontend | React, Vite, TypeScript, tldraw, KaTeX |
| Reminders | Resend e-mail, Telegram Bot API, Web Push |
| Hosting | Docker Compose and Caddy (automatic HTTPS) on a Hetzner server, behind Cloudflare |
| Operations | Ansible (provisioning, deploys, nightly backups), GitHub Actions (CI, releases) |

## Run it yourself

```bash
git clone https://github.com/Durapix/chalkback.git
cd chalkback/deploy
docker compose --env-file local.env up -d --build
```

Then open <http://localhost:8080>. Without an Anthropic API key the AI steps run in a free,
deterministic offline mode. See [Getting started](https://chalkback.xyz/docs/getting-started/)
for development setup and [Deployment](https://chalkback.xyz/docs/deployment/) for production.
