# Chalkback API

FastAPI backend for Chalkback.

```bash
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000/docs
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Configuration is read from environment variables or `.env` (see `.env.example`).
Without `ANTHROPIC_API_KEY` the reconstruction and summary pipeline returns deterministic
mock output.

## Database migrations

The schema is managed by Alembic (`migrations/`). At startup the app upgrades the database to
the latest revision. A database created before migrations existed is stamped as the baseline
first, and its data is kept. After changing `app/models.py`:

```bash
uv run alembic revision --autogenerate -m "what changed"   # then read the generated file
```

`tests/test_migrations.py` fails when the models and the migrations disagree.

## Modules

| Module | Responsibility |
|---|---|
| `app/models.py` | SQLAlchemy models: users (teachers and students), lessons, boards, reminders, push subscriptions |
| `app/migrate.py`, `migrations/` | Alembic migrations, applied at startup |
| `app/routers/` | REST endpoints under `/api` |
| `app/imaging.py` | Upload normalization; PDF pages rendered to PNG with pypdfium2 |
| `app/ingest.py`, `app/importers/drawio.py` | Uploads to boards; exact draw.io import |
| `app/scene.py` | The board scene format, its reading order and transcript |
| `app/flowchart.py` | Reads flowcharts as algorithms and recognizes ER diagrams |
| `app/ai/reconstruct.py`, `app/ai/vision.py` | Board image → scene (Claude vision, validated tool schema) |
| `app/ai/summarize.py` | Lesson boards + notes → student-facing summary (structured outputs) |
| `app/jobs.py` | Background jobs that run the AI steps and record status |
| `app/notify.py`, `app/recap_labels.py` | Reminder rendering and delivery (Telegram, Resend email, Web Push), scheduler logic |
| `app/telegram_bot.py` | Telegram connect links: `/start <code>` and `/stop` (long polling) |
| `app/push.py` | Web Push keys (VAPID) and the allowed push services |
| `app/cli.py` | Server-side commands: teacher accounts, test e-mail and notifications |
