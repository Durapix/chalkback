from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo otherwise)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Role(StrEnum):
    teacher = "teacher"
    student = "student"


class JobStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    # Student-only fields
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    language: Mapped[str] = mapped_column(String(32), default="Serbian")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64))
    remind_by_email: Mapped[bool] = mapped_column(default=True)
    remind_by_telegram: Mapped[bool] = mapped_column(default=False)
    next_lesson_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # One-time code for the student's Telegram connect link (t.me/<bot>?start=<code>).
    telegram_link_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    telegram_link_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(80), default="Mathematics")
    taught_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    summary: Mapped[dict | None] = mapped_column(JSON)
    summary_status: Mapped[JobStatus | None] = mapped_column(Enum(JobStatus, native_enum=False))
    summary_error: Mapped[str | None] = mapped_column(Text)

    boards: Mapped[list["Board"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="Board.position"
    )
    student: Mapped[User] = relationship(foreign_keys=[student_id])


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    # Random, unguessable file name under the uploads dir (served at /files/<name>).
    image_file: Mapped[str | None] = mapped_column(String(128))
    # Imported source document (e.g. draw.io) in the sources dir, and which page this board is.
    source_file: Mapped[str | None] = mapped_column(String(128))
    source_page: Mapped[int] = mapped_column(default=0)
    width: Mapped[int] = mapped_column(default=1600)
    height: Mapped[int] = mapped_column(default=900)

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.pending
    )
    error: Mapped[str | None] = mapped_column(Text)
    # Structured scene extracted by the AI (see app.scene.Scene).
    scene: Mapped[dict | None] = mapped_column(JSON)
    # tldraw store snapshot once the board has been opened/edited in the app.
    snapshot: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    lesson: Mapped[Lesson] = relationship(back_populates="boards")


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("student_id", "lesson_id", "channel", "for_session"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    channel: Mapped[str] = mapped_column(String(16))
    # The upcoming session this reminder was sent for (dedup key).
    for_session: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
