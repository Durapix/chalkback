# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-16

First release: the full loop from whiteboard photo to student reminder, running end to end in
mock-AI mode.

### Added

- **API** (FastAPI): teacher and student accounts with JWT auth, students, lessons, boards,
  reminder log. SQLite for development, PostgreSQL in production.
- **Board reconstruction**: image and PDF uploads (one board per page) are rebuilt by Claude
  vision into a validated scene of text, LaTeX math, shapes, arrows and strokes.
- **Lesson recaps**: per-student summaries (topics, key points, formulas, exercises, practice)
  in the student's language.
- **Reminders**: Telegram and email (Resend) delivery, an idempotent scheduler before each
  student's next lesson, and a "send now" action.
- **Web app** (React + tldraw): teacher and student dashboards, editable boards over the
  original photo, a custom KaTeX math shape, autosave, and a recap panel.
- **Mock mode**: deterministic AI output when no `ANTHROPIC_API_KEY` is set.
- **Landing page** with an animated reconstruction hero and an "autopilot" timeline generated
  from git history.
- **Documentation** site (MkDocs Material).
- **Deployment**: Docker Compose with Caddy (HTTPS) and Postgres, a Hetzner bootstrap script,
  and GitHub Actions for CI, AI PR review, releases and deploys.

[Unreleased]: ../../compare/v0.1.0...HEAD
[0.1.0]: ../../releases/tag/v0.1.0
