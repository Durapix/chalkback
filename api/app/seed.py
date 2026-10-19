"""Fictional demo data. Never put real students here: the demo is public."""

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.reconstruct import mock_scene
from app.ai.summarize import mock_summary
from app.config import get_settings
from app.ingest import Ingested, ingest
from app.models import Board, JobStatus, Lesson, Role, User, utcnow
from app.security import hash_password

DEMO_DRAWIO = Path(__file__).parent / "demo" / "linked_list.drawio"


def _ai_boards() -> list[Board]:
    """A board as the AI reconstruction produces it (mock output, no photo)."""
    return [Board(status=JobStatus.ready, scene=mock_scene(None).model_dump())]


def _drawio_boards() -> list[Board]:
    """Boards imported exactly from a (fictional) draw.io file."""
    result = Ingested()
    ingest(DEMO_DRAWIO.read_bytes(), "", DEMO_DRAWIO.name, result)
    return result.boards


LESSONS = [
    ("Mia Novak", "mia@demo.chalkback", "Binary search", _ai_boards,
     "Searched a sorted array by halving it; moved L, D and S by hand."),
    ("Luka Petrov", "luka@demo.chalkback", "Linked lists", _drawio_boards,
     "Built a singly linked list and followed the next pointers."),
]  # fmt: skip


def seed_demo(db: Session) -> None:
    settings = get_settings()
    if db.scalars(select(User).where(User.email == settings.demo_teacher_email)).first():
        return
    pw = hash_password(settings.demo_password)
    teacher = User(
        email=settings.demo_teacher_email, name="Demo Teacher", password_hash=pw, role=Role.teacher
    )
    db.add(teacher)
    db.flush()
    for i, (name, email, title, boards, notes) in enumerate(LESSONS):
        student = User(
            email=email,
            name=name,
            password_hash=pw,
            role=Role.student,
            teacher_id=teacher.id,
            next_lesson_at=utcnow() + timedelta(days=2 + i),
        )
        db.add(student)
        db.flush()
        lesson = Lesson(
            teacher_id=teacher.id,
            student_id=student.id,
            title=title,
            taught_at=utcnow() - timedelta(days=5 - i),
            notes=notes,
        )
        for position, board in enumerate(boards()):
            board.position = position
            lesson.boards.append(board)
        db.add(lesson)
        db.flush()
        lesson.summary = mock_summary(lesson, name.split()[0]).model_dump()
        lesson.summary_status = JobStatus.ready
    db.commit()
