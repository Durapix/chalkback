"""Telegram connect links: a student opens t.me/<bot>?start=<code>, presses Start, and is
connected for reminders without ever seeing a chat ID.

The bot listens with long polling (getUpdates), so nothing has to be configured on Telegram's
side and no public endpoint is exposed. It only answers private /start and /stop messages.
"""

import asyncio
import logging
import secrets
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import User, utcnow

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"

MESSAGES = {
    "serbian": {
        "linked": "Повезано, {name}! Подсетници о часовима ће стизати овде. "
        "Да их искључиш, пошаљи /stop.",
        "invalid": "Овај линк више не важи. Затражи нови од свог наставника.",
        "hello": "Здраво! Овај бот шаље подсетнике о часовима из Chalkback-а. "
        "Да се повежеш, отвори линк који ти је дао наставник.",
        "stopped": "Готово, подсетници више неће стизати овде.",
        "not_linked": "Овај Telegram налог није повезан ни са једним учеником.",
    },
    "english": {
        "linked": "Connected, {name}! Lesson reminders will arrive here. Send /stop to turn "
        "them off.",
        "invalid": "This link is no longer valid. Ask your teacher for a new one.",
        "hello": "Hi! This bot sends lesson reminders from Chalkback. To connect, open the "
        "link your teacher gave you.",
        "stopped": "Done, reminders will no longer arrive here.",
        "not_linked": "This Telegram account is not connected to any student.",
    },
}


def _msg(key: str, language: str | None = "Serbian", **kwargs: str) -> str:
    texts = MESSAGES.get((language or "").strip().lower(), MESSAGES["serbian"])
    return texts[key].format(**kwargs)


class TelegramNotConfigured(RuntimeError):
    pass


_username: str | None = None


async def bot_username() -> str:
    """The bot's @username (from getMe, cached)."""
    global _username
    token = get_settings().telegram_bot_token
    if not token:
        raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN is not configured")
    if _username is None:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(API.format(token=token, method="getMe"))
        r.raise_for_status()
        _username = r.json()["result"]["username"]
    return _username


async def connect_link(db: Session, student: User) -> dict:
    """A fresh one-time connect link for `student` (replaces any earlier one)."""
    username = await bot_username()
    student.telegram_link_code = secrets.token_urlsafe(16)  # 22 chars of [A-Za-z0-9_-]
    student.telegram_link_expires_at = utcnow() + timedelta(days=get_settings().telegram_link_days)
    db.commit()
    return {
        "url": f"https://t.me/{username}?start={student.telegram_link_code}",
        "expires_at": student.telegram_link_expires_at,
    }


def handle_update(db: Session, update: dict) -> tuple[int, str] | None:
    """React to one Telegram update. Returns (chat_id, reply text), or None to stay silent."""
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    if chat.get("type") != "private" or not text.startswith("/"):
        return None
    chat_id = chat["id"]
    command, _, argument = text.partition(" ")
    command = command.split("@", 1)[0]  # "/start@Bot" in some clients
    argument = argument.strip()

    if command == "/start" and argument:
        student = db.scalars(select(User).where(User.telegram_link_code == argument)).first()
        if student is None or (
            student.telegram_link_expires_at is not None
            and student.telegram_link_expires_at < utcnow()
        ):
            return chat_id, _msg("invalid")
        student.telegram_chat_id = str(chat_id)
        student.remind_by_telegram = True
        student.telegram_link_code = None
        student.telegram_link_expires_at = None
        db.commit()
        log.info("Student %s connected Telegram", student.id)
        return chat_id, _msg("linked", student.language, name=student.name.split()[0])

    if command == "/stop":
        students = db.scalars(select(User).where(User.telegram_chat_id == str(chat_id))).all()
        if not students:
            return chat_id, _msg("not_linked")
        for student in students:
            student.telegram_chat_id = None
            student.remind_by_telegram = False
        db.commit()
        return chat_id, _msg("stopped", students[0].language)

    return chat_id, _msg("hello")


async def poll_forever() -> None:
    """Long-poll Telegram for messages and answer them. Runs for the app's lifetime."""
    token = get_settings().telegram_bot_token
    offset: int | None = None
    delay = 5
    async with httpx.AsyncClient(timeout=70) as client:
        while True:
            try:
                r = await client.post(
                    API.format(token=token, method="getUpdates"),
                    json={"timeout": 50, "offset": offset, "allowed_updates": ["message"]},
                )
                if r.status_code == 409:  # a webhook or another poller is active
                    log.warning("Telegram getUpdates conflict: %s", r.text[:200])
                    await asyncio.sleep(60)
                    continue
                r.raise_for_status()
                for update in r.json().get("result", []):
                    offset = update["update_id"] + 1
                    with SessionLocal() as db:
                        reply = handle_update(db, update)
                    if reply:
                        await client.post(
                            API.format(token=token, method="sendMessage"),
                            json={"chat_id": reply[0], "text": reply[1]},
                        )
                delay = 5
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Telegram polling failed; retrying in %ss", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 300)
