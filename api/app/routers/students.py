from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.models import Reminder, Role, User
from app.notify import latest_summarized_lesson, send_reminder
from app.schemas import ReminderOut, StudentIn, StudentOut, StudentUpdate
from app.security import DB, Teacher, hash_password

router = APIRouter(prefix="/students", tags=["students"])


def own_student(db: DB, teacher: User, student_id: int) -> User:
    student = db.get(User, student_id)
    if student is None or student.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    return student


@router.get("", response_model=list[StudentOut])
def list_students(teacher: Teacher, db: DB):
    return db.scalars(select(User).where(User.teacher_id == teacher.id).order_by(User.name)).all()


@router.post("", response_model=StudentOut, status_code=201)
def create_student(body: StudentIn, teacher: Teacher, db: DB):
    email = body.email.lower()
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    data = body.model_dump(exclude={"password", "email"})
    student = User(
        **data,
        email=email,
        password_hash=hash_password(body.password),
        role=Role.student,
        teacher_id=teacher.id,
    )
    db.add(student)
    db.commit()
    return student


@router.patch("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, body: StudentUpdate, teacher: Teacher, db: DB):
    student = own_student(db, teacher, student_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(student, key, value)
    db.commit()
    return student


@router.post("/{student_id}/remind", response_model=list[ReminderOut])
async def remind_now(student_id: int, teacher: Teacher, db: DB):
    """Send the latest lesson recap to the student right away."""
    student = own_student(db, teacher, student_id)
    lesson = latest_summarized_lesson(db, student)
    if lesson is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No summarized lesson to remind about")
    return await send_reminder(db, student, lesson)


@router.get("/{student_id}/reminders", response_model=list[ReminderOut])
def reminder_log(student_id: int, teacher: Teacher, db: DB):
    own_student(db, teacher, student_id)
    return db.scalars(
        select(Reminder).where(Reminder.student_id == student_id).order_by(Reminder.sent_at.desc())
    ).all()
