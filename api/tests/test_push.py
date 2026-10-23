import asyncio
import json

import pytest
from pywebpush import WebPushException

from app import notify, push
from app.db import SessionLocal
from app.models import Lesson, PushSubscription, User
from tests.conftest import auth

FCM = "https://fcm.googleapis.com/fcm/send/abc123"
KEYS = {"p256dh": "BPub", "auth": "secret"}


@pytest.fixture
def mia(client):
    return auth(client, "mia@demo.chalkback", "demo-password")


def test_public_key_is_stable_and_private_key_stays_private(client, mia):
    first = client.get("/api/push/key", headers=mia).json()["public_key"]
    assert first == client.get("/api/push/key", headers=mia).json()["public_key"]
    assert len(first) == 87  # 65-byte uncompressed P-256 point, base64url
    assert push._key_file().exists()


def test_students_subscribe_and_unsubscribe_devices(client, mia, teacher):
    r = client.post("/api/push/subscriptions", headers=mia, json={"endpoint": FCM, "keys": KEYS})
    assert r.status_code == 204
    client.post("/api/push/subscriptions", headers=mia, json={"endpoint": FCM, "keys": KEYS})
    me = client.get("/api/students/me", headers=mia).json()
    assert me["push_devices"] == 1 and me["remind_by_push"]
    card = next(
        s for s in client.get("/api/students", headers=teacher).json() if s["id"] == me["id"]
    )
    assert card["push_devices"] == 1
    client.post("/api/push/unsubscribe", headers=mia, json={"endpoint": FCM})
    assert client.get("/api/students/me", headers=mia).json()["push_devices"] == 0


def test_only_real_push_services_and_only_students(client, mia, teacher):
    for endpoint in (
        "https://evil.example.com/x",
        "http://fcm.googleapis.com/x",
        "https://fcm.googleapis.com.evil.com/x",
    ):
        r = client.post(
            "/api/push/subscriptions", headers=mia, json={"endpoint": endpoint, "keys": KEYS}
        )
        assert r.status_code == 422, endpoint
    assert push.is_push_endpoint("https://web.push.apple.com/QGuQ")
    assert push.is_push_endpoint("https://wns2-db5p.notify.windows.com/w/?token=x")
    r = client.post(
        "/api/push/subscriptions", headers=teacher, json={"endpoint": FCM, "keys": KEYS}
    )
    assert r.status_code == 403


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def test_push_reminders_reach_devices_and_forget_gone_ones(client, mia, monkeypatch):
    client.post("/api/push/subscriptions", headers=mia, json={"endpoint": FCM, "keys": KEYS})
    gone = "https://updates.push.services.mozilla.com/wpush/v2/gone"
    client.post("/api/push/subscriptions", headers=mia, json={"endpoint": gone, "keys": KEYS})
    sent = []

    def fake_webpush(info, data, **kwargs):
        if info["endpoint"] == gone:
            raise WebPushException("gone", response=FakeResponse(410))
        sent.append((info["endpoint"], json.loads(data), kwargs["vapid_claims"]))

    monkeypatch.setattr(notify, "webpush", fake_webpush)
    monkeypatch.setattr(notify, "is_demo_student", lambda db, student: False)
    with SessionLocal() as db:
        student = db.query(User).filter_by(email="mia@demo.chalkback").one()
        lesson = db.query(Lesson).filter_by(student_id=student.id).first()
        assert "push" in notify.channels_for(student)
        results = asyncio.run(notify.send_reminder(db, student, lesson))
        assert {r.channel: r.status for r in results}["push"] == "sent"
        assert db.query(PushSubscription).filter_by(endpoint=gone).count() == 0
    (endpoint, payload, claims) = sent[0]
    assert endpoint == FCM and payload["url"].endswith(f"/lessons/{lesson.id}")
    assert payload["title"] and payload["body"] and claims["sub"].startswith("http")


def test_turning_push_off_skips_the_channel(client, mia, teacher):
    client.post("/api/push/subscriptions", headers=mia, json={"endpoint": FCM, "keys": KEYS})
    sid = client.get("/api/students/me", headers=mia).json()["id"]
    client.patch(f"/api/students/{sid}", headers=teacher, json={"remind_by_push": False})
    with SessionLocal() as db:
        assert "push" not in notify.channels_for(db.get(User, sid))
