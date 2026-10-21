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


def test_main_prompts_for_the_password(client, monkeypatch, capsys):
    answers = iter(["typed-password-1", "typed-password-1"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    code = cli.main(["create-teacher", "--email", "cli@example.org", "--name", "Cli"])
    assert code == 0 and "Created teacher cli@example.org" in capsys.readouterr().out
    mismatch = iter(["one-password-1", "other-password"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(mismatch))
    assert cli.main(["set-password", "--email", "cli@example.org"]) == 1
