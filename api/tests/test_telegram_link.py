from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app import telegram_bot
from app.db import SessionLocal
from app.models import User, utcnow
from tests.conftest import auth


@pytest.fixture
def bot(monkeypatch):
    async def username():
        return "Chalkback_recap_bot"

    monkeypatch.setattr(telegram_bot, "bot_username", username)


def start(code: str, chat_id: int = 555, chat_type: str = "private") -> dict:
    return {
        "update_id": 1,
        "message": {"chat": {"id": chat_id, "type": chat_type}, "text": f"/start {code}"},
    }


def link_code(client, headers, student_id) -> str:
    r = client.post(f"/api/students/{student_id}/telegram-link", headers=headers)
    assert r.status_code == 200, r.text
    url = urlparse(r.json()["url"])
    assert url.netloc == "t.me" and url.path == "/Chalkback_recap_bot"
    return parse_qs(url.query)["start"][0]


def test_pressing_start_connects_the_student_once(client, teacher, bot):
    student = client.get("/api/students", headers=teacher).json()[0]
    code = link_code(client, teacher, student["id"])
    with SessionLocal() as db:
        chat_id, reply = telegram_bot.handle_update(db, start(code))
        assert chat_id == 555 and reply.startswith("Повезано")
        user = db.get(User, student["id"])
        assert (user.telegram_chat_id, user.remind_by_telegram) == ("555", True)
        assert user.telegram_link_code is None
        # The link works once.
        assert "не важи" in telegram_bot.handle_update(db, start(code, chat_id=666))[1]
    shown = client.get("/api/students", headers=teacher).json()[0]
    assert shown["telegram_chat_id"] == "555" and shown["remind_by_telegram"]


def test_new_link_replaces_the_old_and_links_expire(client, teacher, bot):
    student = client.get("/api/students", headers=teacher).json()[0]
    old = link_code(client, teacher, student["id"])
    new = link_code(client, teacher, student["id"])
    with SessionLocal() as db:
        assert "не важи" in telegram_bot.handle_update(db, start(old))[1]
        user = db.get(User, student["id"])
        user.telegram_link_expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
        assert "не важи" in telegram_bot.handle_update(db, start(new))[1]
        assert db.get(User, student["id"]).telegram_chat_id is None


def test_stop_disconnects_and_groups_are_ignored(client, teacher, bot):
    student = client.get("/api/students", headers=teacher).json()[0]
    code = link_code(client, teacher, student["id"])
    with SessionLocal() as db:
        assert telegram_bot.handle_update(db, start(code, chat_type="group")) is None
        telegram_bot.handle_update(db, start(code))
        stop = {
            "update_id": 2,
            "message": {"chat": {"id": 555, "type": "private"}, "text": "/stop"},
        }
        assert "више неће" in telegram_bot.handle_update(db, stop)[1]
        user = db.get(User, student["id"])
        assert (user.telegram_chat_id, user.remind_by_telegram) == (None, False)
        hello = {
            "update_id": 3,
            "message": {"chat": {"id": 9, "type": "private"}, "text": "/start"},
        }
        assert "Здраво" in telegram_bot.handle_update(db, hello)[1]


def test_students_get_their_own_link_and_see_if_connected(client, bot):
    mia = auth(client, "mia@demo.chalkback", "demo-password")
    me = client.get("/api/students/me", headers=mia).json()
    assert me["email"] == "mia@demo.chalkback" and me["telegram_chat_id"] is None
    r = client.post("/api/students/me/telegram-link", headers=mia)
    assert r.status_code == 200 and "start=" in r.json()["url"]


def test_links_need_a_bot_and_the_right_teacher(client, teacher, monkeypatch):
    monkeypatch.setattr(telegram_bot.get_settings(), "telegram_bot_token", None)
    student = client.get("/api/students", headers=teacher).json()[0]
    r = client.post(f"/api/students/{student['id']}/telegram-link", headers=teacher)
    assert r.status_code == 409
    assert client.post("/api/students/99999/telegram-link", headers=teacher).status_code == 404
    assert client.get("/api/students/me", headers=teacher).status_code == 403
