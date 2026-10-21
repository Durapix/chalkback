"""Server-side account commands. Passwords are typed at a prompt, never passed as arguments.

On the server (prefix each with `docker exec -it chalkback-api-1`):
    python -m app.cli list-teachers
    python -m app.cli create-teacher --email you@example.com --name "Your Name"
    python -m app.cli set-email --email typo@example.con --new-email you@example.com
    python -m app.cli set-password --email you@example.com
    python -m app.cli delete-teacher --email typo@example.con
    python -m app.cli send-test-email --to you@example.com
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import notify
from app.config import get_settings
from app.db import SessionLocal
from app.models import Lesson, Role, User
from app.security import hash_password

MIN_PASSWORD = 8


class CliError(Exception):
    pass


def _normalize(email: str) -> str:
    email = email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email:
        raise CliError(f"Not an e-mail address: {email}")
    return email


def _find(db: Session, email: str) -> User:
    user = db.scalars(select(User).where(User.email == email.strip().lower())).first()
    if user is None:
        raise CliError(f"No account for {email}")
    return user


def _teacher(db: Session, email: str) -> User:
    user = _find(db, email)
    if user.role != Role.teacher:
        raise CliError(f"{user.email} is a student account, not a teacher")
    if user.email == get_settings().demo_teacher_email:
        raise CliError("The demo teacher cannot be changed here")
    return user


def _taken(db: Session, email: str) -> None:
    if db.scalars(select(User).where(User.email == email)).first():
        raise CliError(f"{email} already has an account")


def _counts(db: Session, teacher: User) -> tuple[int, int]:
    """(students, lessons) of a teacher."""
    return (
        db.scalar(select(func.count()).select_from(User).where(User.teacher_id == teacher.id)),
        db.scalar(select(func.count()).select_from(Lesson).where(Lesson.teacher_id == teacher.id)),
    )


def list_teachers(db: Session) -> list[tuple[User, int, int]]:
    """Every teacher with their number of students and lessons."""
    teachers = db.scalars(select(User).where(User.role == Role.teacher).order_by(User.id)).all()
    return [(t, *_counts(db, t)) for t in teachers]


def create_teacher(db: Session, email: str, name: str, password: str) -> User:
    email = _normalize(email)
    _taken(db, email)
    _check(password)
    user = User(
        email=email, name=name.strip(), password_hash=hash_password(password), role=Role.teacher
    )
    db.add(user)
    db.commit()
    return user


def set_email(db: Session, email: str, new_email: str) -> User:
    user = _teacher(db, email)
    new_email = _normalize(new_email)
    _taken(db, new_email)
    user.email = new_email
    db.commit()
    return user


def set_password(db: Session, email: str, password: str) -> User:
    user = _find(db, email)
    _check(password)
    user.password_hash = hash_password(password)
    db.commit()
    return user


def delete_teacher(db: Session, email: str) -> None:
    """Delete a teacher account that has no students or lessons (e.g. one with a mistyped
    address). Accounts with data are refused: fix their address with set-email instead."""
    user = _teacher(db, email)
    if _counts(db, user) != (0, 0):
        raise CliError(
            f"{user.email} has students or lessons; use set-email to correct the address"
        )
    db.delete(user)
    db.commit()


# A fictional recap in Serbian, rendered with the real reminder templates.
SAMPLE_SUMMARY = {
    "headline": "Пробна порука: Chalkback подсетник ради",
    "recap_message": (
        "Здраво! Ово је пробни подсетник из Chalkback-а. Ако га читаш, слање е-поште "
        "преко Resend-а ради."
    ),
    "key_points": ["Домен chalkback.xyz је потврђен за слање.", "Наслови су на српском."],
    "review_suggestions": ["Нема ништа да урадиш: ово је само проба."],
    "language": "Serbian",
}


async def send_test_email(to: str) -> str:
    """Send a sample recap reminder to `to` through the configured e-mail provider. Nothing is
    stored: the student and lesson exist only in memory."""
    to = _normalize(to)
    student = User(name="Test", email=to, language="Serbian")
    lesson = Lesson(id=0, title="Пробни час", summary=SAMPLE_SUMMARY)
    labels = notify.labels_for(student, lesson)
    subject = labels.subject.format(headline=SAMPLE_SUMMARY["headline"])
    try:
        await notify.send_email(
            to,
            subject,
            notify.render_text(student, lesson),
            notify.render_html(student, lesson),
        )
    except notify.DeliveryError as exc:
        raise CliError(str(exc)) from exc
    return subject


def _check(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise CliError(f"The password needs at least {MIN_PASSWORD} characters")


def _prompt_password() -> str:
    first = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != first:
        raise CliError("The passwords do not match")
    return first


def _confirm(question: str) -> None:
    if input(f"{question} [y/N] ").strip().lower() not in ("y", "yes"):
        raise CliError("Cancelled, nothing changed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-teachers", help="List teacher accounts")
    create = sub.add_parser("create-teacher", help="Create a teacher account")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    rename = sub.add_parser("set-email", help="Correct a teacher's e-mail address")
    rename.add_argument("--email", required=True)
    rename.add_argument("--new-email", required=True)
    reset = sub.add_parser("set-password", help="Set a new password for an existing account")
    reset.add_argument("--email", required=True)
    delete = sub.add_parser("delete-teacher", help="Delete a teacher with no students or lessons")
    delete.add_argument("--email", required=True)
    test_mail = sub.add_parser("send-test-email", help="Send a sample reminder (stores nothing)")
    test_mail.add_argument("--to", required=True)
    args = parser.parse_args(argv)

    try:
        with SessionLocal() as db:
            if args.command == "list-teachers":
                for t, students, lessons in list_teachers(db):
                    print(f"{t.email}  ({t.name}; {students} students, {lessons} lessons)")
            elif args.command == "create-teacher":
                email = _normalize(args.email)
                _confirm(f"Create teacher {email} ({args.name.strip()})?")
                user = create_teacher(db, email, args.name, _prompt_password())
                print(f"Created teacher {user.email}. Sign in at /app/.")
            elif args.command == "set-email":
                new_email = _normalize(args.new_email)
                _confirm(f"Change {args.email.strip().lower()} to {new_email}?")
                user = set_email(db, args.email, new_email)
                print(f"The account now signs in as {user.email}.")
            elif args.command == "set-password":
                user = set_password(db, args.email, _prompt_password())
                print(f"Password updated for {user.email}.")
            elif args.command == "send-test-email":
                subject = asyncio.run(send_test_email(args.to))
                print(f"Sent “{subject}” to {args.to.strip().lower()}.")
            else:
                _confirm(f"Delete teacher {args.email.strip().lower()}?")
                delete_teacher(db, args.email)
                print("Deleted.")
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
