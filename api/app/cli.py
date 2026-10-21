"""Server-side account commands. Passwords are typed at a prompt, never passed as arguments.

On the server:
    docker exec -it chalkback-api-1 python -m app.cli create-teacher --email you@example.com \
        --name "Your Name"
    docker exec -it chalkback-api-1 python -m app.cli set-password --email you@example.com
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Role, User
from app.security import hash_password

MIN_PASSWORD = 8


class CliError(Exception):
    pass


def create_teacher(db: Session, email: str, name: str, password: str) -> User:
    email = email.strip().lower()
    if "@" not in email:
        raise CliError(f"Not an e-mail address: {email}")
    if db.scalars(select(User).where(User.email == email)).first():
        raise CliError(f"{email} already has an account (use set-password to change it)")
    _check(password)
    user = User(
        email=email, name=name.strip(), password_hash=hash_password(password), role=Role.teacher
    )
    db.add(user)
    db.commit()
    return user


def set_password(db: Session, email: str, password: str) -> User:
    user = db.scalars(select(User).where(User.email == email.strip().lower())).first()
    if user is None:
        raise CliError(f"No account for {email}")
    _check(password)
    user.password_hash = hash_password(password)
    db.commit()
    return user


def _check(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise CliError(f"The password needs at least {MIN_PASSWORD} characters")


def _prompt_password() -> str:
    first = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != first:
        raise CliError("The passwords do not match")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-teacher", help="Create a teacher account")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    reset = sub.add_parser("set-password", help="Set a new password for an existing account")
    reset.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    try:
        password = _prompt_password()
        with SessionLocal() as db:
            if args.command == "create-teacher":
                user = create_teacher(db, args.email, args.name, password)
                print(f"Created teacher {user.email}. Sign in at /app/.")
            else:
                user = set_password(db, args.email, password)
                print(f"Password updated for {user.email}.")
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
