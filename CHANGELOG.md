# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security

- Pillow 12.3 → 13.0 (24 CVEs; it decodes uploaded board images) and certifi 2026.10.19.
- Deploys pull fresh base images, so fixes such as Node.js 22.23.4 (October 2026 security
  release, CVE-2026-111497 and others) reach the web build. Previously cached images were reused.
- GitHub Actions are pinned to commit SHAs instead of movable tags.
- Reminders for the public demo teacher's students are logged as `skipped` and never delivered,
  so the demo login cannot be used to send e-mail or Telegram messages to anyone.

### Added

- **Icons at every size** from the existing logo (`branding/`): Telegram bot picture, iPhone and
  Android home-screen icons, `.ico` fallback, and a web app manifest for the app.
- `python -m app.cli`: server-side account commands for production, where registration is closed:
  `list-teachers`, `create-teacher` (confirms the address first), `set-email` (fix a typo),
  `set-password`, `delete-teacher` (only accounts without students or lessons), and `send-test-email`
  (a sample reminder through the real templates and Resend, storing nothing).

## [0.2.0] - 2026-10-21

Live at https://chalkback.xyz: real lesson boards imported exactly, recaps that read them, and an
Ansible-managed server with backups and migrations.

### Added

- **Ansible provisioning and deploys** (`deploy/ansible`). One playbook hardens a fresh Ubuntu
  server (key-only SSH, ufw, fail2ban, unattended upgrades, swap), installs Docker, and ships
  `main` with `git archive`, so only tracked files ever leave the machine. It generates the
  database password and JWT secret on the server and waits for HTTPS health. It runs from a
  container, so it works on Windows. The CI deploy workflow uses the same playbook. This
  replaces `bootstrap-server.sh` and `deploy.sh`.
- **Database migrations** (Alembic). The app upgrades its schema at startup; existing databases
  are stamped as the baseline and keep their data. A test fails if models and migrations drift.
- **Nightly backups** of the database and uploads on the server (Ansible role `backup`, 14 days),
  with restore steps in the deployment docs.
- **Entity-relationship diagrams** are recognized and explained as data models, not algorithms.
- Recap section titles (and reminder e-mail subject and button) follow the recap's language.
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

- **draw.io fidelity.** Table cells keep their fill colors and headers (red/green filtering
  steps on database boards). Labels are fitted so shapes never grow into each other. Wires
  routed through waypoints are kept. Lines end on rotated shapes, and west-facing trapezoids are flipped.
- Recaps say so honestly when a board is thin or partial, and read red/green table marks.
- Serbian recaps are always written in Cyrillic, and new students default to Serbian.
- **Recaps understand flowcharts.** Boards' flowcharts are read as algorithms: START/INPUT/
  OUTPUT, IF and REPEAT with branch labels (including T/F written next to arrows), boxed or
  joined shapes as units, called boxes as calls and recursion, and titles above or below a
  chart. The recap prompt asks what each algorithm computes, and the offline recap describes
  their structure instead of repeating labels.

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

[Unreleased]: ../../compare/v0.2.0...HEAD
[0.2.0]: ../../releases/tag/v0.2.0
[0.1.0]: ../../releases/tag/v0.1.0
