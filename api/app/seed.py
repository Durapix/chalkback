"""Fictional demo data. Never put real students here: the demo is public."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.reconstruct import mock_scene
from app.ai.summarize import mock_summary
from app.config import get_settings
from app.models import Board, JobStatus, Lesson, Role, User, utcnow
from app.security import hash_password

STUDENTS = [
    ("Mia Novak", "mia@demo.chalkback"),
    ("Luka Petrov", "luka@demo.chalkback"),
]


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
    for i, (name, email) in enumerate(STUDENTS):
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
            title="Quadratic equations",
            taught_at=utcnow() - timedelta(days=5 - i),
            notes="Introduced the discriminant; solved three equations together.",
        )
        lesson.boards.append(
            Board(position=0, status=JobStatus.ready, scene=mock_scene(None).model_dump())
        )
        db.add(lesson)
        db.flush()
        lesson.summary = mock_summary(lesson, name.split()[0]).model_dump()
        lesson.summary_status = JobStatus.ready
    db.commit()
