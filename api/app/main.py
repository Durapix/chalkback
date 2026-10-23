import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import SessionLocal, engine
from app.migrate import upgrade_db
from app.notify import dispatch_due_reminders
from app.routers import auth, boards, lessons, students
from app.seed import seed_demo
from app.telegram_bot import poll_forever

log = logging.getLogger("chalkback")


async def reminder_tick() -> None:
    with SessionLocal() as db:
        sent = await dispatch_due_reminders(db)
    if sent:
        log.info("Sent %d reminders", sent)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    upgrade_db(engine)
    if settings.seed_demo:
        with SessionLocal() as db:
            seed_demo(db)
    if not settings.ai_enabled:
        log.warning("ANTHROPIC_API_KEY not set: AI pipeline runs in mock mode")

    scheduler = None
    if settings.scheduler_enabled:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(reminder_tick, "interval", minutes=settings.reminder_interval_minutes)
        scheduler.start()
    telegram = None
    if settings.scheduler_enabled and settings.telegram_polling and settings.telegram_bot_token:
        telegram = asyncio.create_task(poll_forever())
    yield
    if telegram:
        telegram.cancel()
    if scheduler:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title=f"{settings.app_name} API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (auth, students, lessons, boards):
        app.include_router(module.router, prefix="/api")

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"status": "ok", "ai": "claude" if settings.ai_enabled else "mock"}

    # Board images. File names are random 192-bit tokens (capability URLs).
    app.mount("/files", StaticFiles(directory=settings.uploads_dir), name="files")
    return app


app = create_app()
