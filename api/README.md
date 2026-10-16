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

## Modules

| Module | Responsibility |
|---|---|
| `app/models.py` | SQLAlchemy models: users (teachers and students), lessons, boards, reminders |
| `app/routers/` | REST endpoints under `/api` |
| `app/imaging.py` | Upload normalization; PDF pages rendered to PNG with pypdfium2 |
| `app/ai/scene.py` | The structured scene format Claude returns for a board |
| `app/ai/reconstruct.py` | Board image → scene (Claude vision + structured outputs) |
| `app/ai/summarize.py` | Lesson boards + notes → student-facing summary |
| `app/jobs.py` | Background jobs that run the AI steps and record status |
| `app/notify.py` | Reminder rendering and delivery (Telegram, Resend email), scheduler logic |
