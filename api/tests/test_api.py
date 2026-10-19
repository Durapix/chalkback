import asyncio
import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image

from app import notify
from app.db import SessionLocal
from tests.conftest import auth


def png_bytes(w=800, h=450) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "ai": "mock"}


def test_login_rejects_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "teacher@demo.chalkback", "password": "nope"})
    assert r.status_code == 401


def test_requires_auth(client):
    assert client.get("/api/lessons").status_code == 401


def test_demo_seed_visible_to_teacher_and_student(client, teacher):
    lessons = client.get("/api/lessons", headers=teacher).json()
    assert len(lessons) == 2
    assert all(lesson["summary_status"] == "ready" for lesson in lessons)

    mia = auth(client, "mia@demo.chalkback", "demo-password")
    own = client.get("/api/lessons", headers=mia).json()
    assert [lesson["student"]["name"] for lesson in own] == ["Mia Novak"]
    other = next(lesson for lesson in lessons if lesson["student"]["name"] != "Mia Novak")
    assert client.get(f"/api/lessons/{other['id']}", headers=mia).status_code == 404


def test_students_cannot_manage(client):
    mia = auth(client, "mia@demo.chalkback", "demo-password")
    assert client.get("/api/students", headers=mia).status_code == 403


def test_full_lesson_flow(client, teacher):
    r = client.post(
        "/api/students",
        headers=teacher,
        json={"name": "Ana Test", "email": "ana@example.org", "password": "password123"},
    )
    assert r.status_code == 201, r.text
    student_id = r.json()["id"]

    r = client.post(
        "/api/lessons", headers=teacher, json={"student_id": student_id, "title": "Vectors"}
    )
    assert r.status_code == 201, r.text
    lesson_id = r.json()["id"]

    # Upload -> background reconstruction (mock) runs before TestClient returns.
    r = client.post(
        f"/api/lessons/{lesson_id}/boards",
        headers=teacher,
        files=[("files", ("board.png", png_bytes(), "image/png"))],
    )
    assert r.status_code == 201, r.text
    board_id = r.json()[0]["id"]

    board = client.get(f"/api/boards/{board_id}", headers=teacher).json()
    assert board["status"] == "ready"
    assert board["width"] == 800
    assert {el["kind"] for el in board["scene"]["elements"]} >= {"note", "code", "connector"}
    image = client.get(board["image_url"].replace("http://testserver", ""))
    assert image.status_code == 200

    r = client.put(
        f"/api/boards/{board_id}/snapshot", headers=teacher, json={"snapshot": {"document": {}}}
    )
    assert r.json()["snapshot"] == {"document": {}}

    r = client.post(f"/api/lessons/{lesson_id}/summarize", headers=teacher)
    assert r.status_code == 202
    lesson = client.get(f"/api/lessons/{lesson_id}", headers=teacher).json()
    assert lesson["summary_status"] == "ready"
    assert "Ana" in lesson["summary"]["recap_message"]


def test_upload_rejects_unknown_type(client, teacher):
    lesson_id = client.get("/api/lessons", headers=teacher).json()[0]["id"]
    r = client.post(
        f"/api/lessons/{lesson_id}/boards",
        headers=teacher,
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert r.status_code == 415


def test_pdf_upload_creates_board_per_page(client, teacher):
    pages = [Image.new("RGB", (600, 400), "white") for _ in range(2)]
    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])
    lesson_id = client.get("/api/lessons", headers=teacher).json()[0]["id"]
    r = client.post(
        f"/api/lessons/{lesson_id}/boards",
        headers=teacher,
        files=[("files", ("boards.pdf", buf.getvalue(), "application/pdf"))],
    )
    assert r.status_code == 201, r.text
    assert len(r.json()) == 2


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    async def fake_telegram(chat_id, text):
        sent.append(("telegram", chat_id, text))

    async def fake_email(to, subject, text, html_body):
        sent.append(("email", to, subject))

    monkeypatch.setattr(notify, "send_telegram", fake_telegram)
    monkeypatch.setattr(notify, "send_email", fake_email)
    return sent


def test_manual_reminder(client, teacher, outbox):
    student = client.get("/api/students", headers=teacher).json()[0]
    client.patch(
        f"/api/students/{student['id']}",
        headers=teacher,
        json={"telegram_chat_id": "12345", "remind_by_telegram": True},
    )
    r = client.post(f"/api/students/{student['id']}/remind", headers=teacher)
    assert r.status_code == 200, r.text
    assert sorted(x["channel"] for x in r.json()) == ["email", "telegram"]
    assert {x[0] for x in outbox} == {"email", "telegram"}
    log = client.get(f"/api/students/{student['id']}/reminders", headers=teacher).json()
    assert len(log) == 2


def test_scheduled_reminders_are_idempotent(client, teacher, outbox):
    student = client.get("/api/students", headers=teacher).json()[0]
    soon = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    client.patch(f"/api/students/{student['id']}", headers=teacher, json={"next_lesson_at": soon})
    with SessionLocal() as db:
        first = asyncio.run(notify.dispatch_due_reminders(db))
        second = asyncio.run(notify.dispatch_due_reminders(db))
    assert first == 1  # email only for this student
    assert second == 0


def test_failed_multi_upload_leaves_no_files(client, teacher):
    from app.config import get_settings

    uploads = get_settings().uploads_dir
    before = set(uploads.iterdir())
    lesson_id = client.get("/api/lessons", headers=teacher).json()[0]["id"]
    r = client.post(
        f"/api/lessons/{lesson_id}/boards",
        headers=teacher,
        files=[
            ("files", ("ok.png", png_bytes(), "image/png")),
            ("files", ("bad.txt", b"x", "text/plain")),
        ],
    )
    assert r.status_code == 415
    assert set(uploads.iterdir()) == before


def test_deleting_lesson_removes_images(client, teacher):
    from app.config import get_settings

    lesson_id = client.get("/api/lessons", headers=teacher).json()[0]["id"]
    boards = client.post(
        f"/api/lessons/{lesson_id}/boards",
        headers=teacher,
        files=[("files", ("ok.png", png_bytes(), "image/png"))],
    ).json()
    name = boards[0]["image_url"].rsplit("/", 1)[1]
    assert (get_settings().uploads_dir / name).exists()
    assert client.delete(f"/api/lessons/{lesson_id}", headers=teacher).status_code == 204
    assert not (get_settings().uploads_dir / name).exists()


def test_drawio_upload_is_ready_at_once_and_reimportable(client, teacher):
    from app.config import get_settings
    from tests.test_import import FIXTURE

    settings = get_settings()
    lesson_id = client.get("/api/lessons", headers=teacher).json()[0]["id"]
    sources_before = set(settings.sources_dir.iterdir())
    r = client.post(
        f"/api/lessons/{lesson_id}/boards",
        headers=teacher,
        files=[("files", ("lesson.drawio", FIXTURE.read_bytes(), "application/octet-stream"))],
    )
    assert r.status_code == 201, r.text
    boards = r.json()
    assert [b["status"] for b in boards] == ["ready", "ready"]
    assert [b["title"] for b in boards] == ["Linked list", "Flowchart"]
    assert all(b["image_url"] is None for b in boards)

    board = client.get(f"/api/boards/{boards[0]['id']}", headers=teacher).json()
    assert board["scene"]["source"] == "drawio"
    (pic,) = [el for el in board["scene"]["elements"] if el["kind"] == "image"]
    assert client.get(f"/files/{pic['file']}").status_code == 200
    # The original document is kept for re-import but never served.
    (source,) = set(settings.sources_dir.iterdir()) - sources_before
    assert client.get(f"/files/{source.name}").status_code == 404

    client.put(f"/api/boards/{board['id']}/snapshot", headers=teacher, json={"snapshot": {"a": 1}})
    again = client.post(f"/api/boards/{board['id']}/reconstruct", headers=teacher).json()
    assert again["status"] == "ready" and again["snapshot"] is None
    (pic2,) = [el for el in again["scene"]["elements"] if el["kind"] == "image"]
    assert not (settings.uploads_dir / pic["file"]).exists()
    assert (settings.uploads_dir / pic2["file"]).exists()

    # Deleting one page keeps the shared source; deleting the lesson removes everything.
    client.delete(f"/api/boards/{boards[1]['id']}", headers=teacher)
    assert source.exists()
    client.delete(f"/api/lessons/{lesson_id}", headers=teacher)
    assert not source.exists()
    assert not (settings.uploads_dir / pic2["file"]).exists()


def test_broken_drawio_upload_is_rejected(client, teacher):
    lesson_id = client.get("/api/lessons", headers=teacher).json()[0]["id"]
    r = client.post(
        f"/api/lessons/{lesson_id}/boards",
        headers=teacher,
        files=[("files", ("x.drawio", b"<mxfile><diagram>%%%</diagram></mxfile>", "text/xml"))],
    )
    assert r.status_code == 422
