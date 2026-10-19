# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Exact draw.io import.** HTML exports, `.drawio` and `.xml` files become boards immediately,
  with no AI and no cost. Shapes, colors, labels, opacity, tables, groups, pen ink and embedded
  images are kept, and connectors stay attached to their shapes. Each page is one board, and
  boards can be re-imported from the stored source.
- **Board vocabulary for real lessons.** Sticky notes and note grids, code blocks, frames,
  picture regions, and connectors attached to elements, for both draw.io and AI-reconstructed
  boards.
- A fictional draw.io demo lesson ("Linked lists") in the seed data.
- Running the production Docker stack locally (`deploy/local.env`).

### Changed

- Board reconstruction sends its vocabulary as a validated tool schema instead of structured
  outputs, which rejected it as too large. It streams, with room for dense boards. Tested on two
  real Miro collages for $0.37 in total.
- AI-read text, sticker and shape labels are sized to fit what they cover.

- The AI reconstruction prompt and schema target the real board material: Miro screenshots of
  programming, math, electronics and database lessons, often stitched into collages.
- Deploy and AI review workflows stay off until `DEPLOY_ENABLED` / `AI_REVIEW_ENABLED` are set.

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
