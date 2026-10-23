import pytest

from app import cli
from app.db import SessionLocal
from app.security import verify_password
from tests.conftest import auth


def test_create_teacher_and_sign_in(client):
    with SessionLocal() as db:
        user = cli.create_teacher(db, " New.Teacher@Example.org ", "New Teacher", "long-enough-1")
    assert user.email == "new.teacher@example.org" and user.role == "teacher"
    assert auth(client, "new.teacher@example.org", "long-enough-1")


def test_create_teacher_refuses_duplicates_and_short_passwords(client):
    with SessionLocal() as db:
        with pytest.raises(cli.CliError, match="already has an account"):
            cli.create_teacher(db, "teacher@demo.chalkback", "Again", "long-enough-1")
        with pytest.raises(cli.CliError, match="at least"):
            cli.create_teacher(db, "short@example.org", "Short", "1234567")


def test_set_password(client):
    with SessionLocal() as db:
        user = cli.set_password(db, "teacher@demo.chalkback", "a-new-password")
        assert verify_password("a-new-password", user.password_hash)
        with pytest.raises(cli.CliError, match="No account"):
            cli.set_password(db, "nobody@example.org", "a-new-password")


def test_mistyped_teacher_email_can_be_corrected_or_deleted(client):
    with SessionLocal() as db:
        cli.create_teacher(db, "me@exmaple.org", "Me", "long-enough-1")
        cli.create_teacher(db, "me@typo.org", "Me", "long-enough-1")
        user = cli.set_email(db, "me@exmaple.org", "Me@Example.org")
        assert user.email == "me@example.org"
        cli.delete_teacher(db, "me@typo.org")
        emails = [t.email for t, _, _ in cli.list_teachers(db)]
        assert "me@example.org" in emails and "me@typo.org" not in emails
        with pytest.raises(cli.CliError, match="demo teacher"):
            cli.delete_teacher(db, "teacher@demo.chalkback")
        with pytest.raises(cli.CliError, match="already has an account"):
            cli.set_email(db, "me@example.org", "teacher@demo.chalkback")
        with pytest.raises(cli.CliError, match="Not an e-mail"):
            cli.set_email(db, "me@example.org", "me@example")
    assert auth(client, "me@example.org", "long-enough-1")


def test_teachers_with_data_are_not_deleted(client, teacher):
    with SessionLocal() as db:
        cli.create_teacher(db, "busy@example.org", "Busy", "long-enough-1")
    busy = auth(client, "busy@example.org", "long-enough-1")
    client.post(
        "/api/students",
        headers=busy,
        json={"name": "S", "email": "s@example.org", "password": "password123"},
    )
    with SessionLocal() as db, pytest.raises(cli.CliError, match="has students or lessons"):
        cli.delete_teacher(db, "busy@example.org")


def test_main_prompts_for_the_password(client, monkeypatch, capsys):
    answers = iter(["typed-password-1", "typed-password-1"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    code = cli.main(["create-teacher", "--email", "cli@example.org", "--name", "Cli"])
    assert code == 0 and "Created teacher cli@example.org" in capsys.readouterr().out
    mismatch = iter(["one-password-1", "other-password"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(mismatch))
    assert cli.main(["set-password", "--email", "cli@example.org"]) == 1


def test_main_asks_before_creating(client, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    code = cli.main(["create-teacher", "--email", "Oops@Example.org", "--name", "Oops"])
    assert code == 1 and "Cancelled" in capsys.readouterr().err
    with SessionLocal() as db:
        assert "oops@example.org" not in [t.email for t, _, _ in cli.list_teachers(db)]


def test_send_test_email_uses_the_reminder_templates_and_stores_nothing(client, monkeypatch):
    sent = []

    async def fake_email(to, subject, text, html_body):
        sent.append((to, subject, text, html_body))

    monkeypatch.setattr(cli.notify, "send_email", fake_email)
    assert cli.main(["send-test-email", "--to", "Me@Example.org"]) == 0
    (to, subject, text, html_body) = sent[0]
    assert to == "me@example.org" and subject.startswith("Подсетник: ")
    assert "Најважније:" in text and "Пре следећег часа" in html_body
    with SessionLocal() as db:
        from app.models import Lesson, User

        assert db.query(User).filter_by(email="me@example.org").count() == 0
        assert db.query(Lesson).filter_by(title="Пробни час").count() == 0


def test_send_test_email_reports_delivery_errors(client, monkeypatch, capsys):
    async def failing(*args):
        raise cli.notify.DeliveryError("RESEND_API_KEY is not configured")

    monkeypatch.setattr(cli.notify, "send_email", failing)
    assert cli.main(["send-test-email", "--to", "me@example.org"]) == 1
    assert "RESEND_API_KEY" in capsys.readouterr().err


def test_send_test_push_reaches_the_students_devices(client, monkeypatch, capsys):
    mia = auth(client, "mia@demo.chalkback", "demo-password")
    sent = []
    monkeypatch.setattr(cli.notify, "webpush", lambda info, data, **kw: sent.append(info))
    assert cli.main(["send-test-push", "--email", "mia@demo.chalkback"]) == 1
    assert "not turned on notifications" in capsys.readouterr().err
    client.post(
        "/api/push/subscriptions",
        headers=mia,
        json={"endpoint": "https://fcm.googleapis.com/x", "keys": {"p256dh": "k", "auth": "a"}},
    )
    assert cli.main(["send-test-push", "--email", "mia@demo.chalkback"]) == 0
    assert sent[0]["endpoint"] == "https://fcm.googleapis.com/x"
