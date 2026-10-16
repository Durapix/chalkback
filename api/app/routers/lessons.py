from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy import select

from app.config import get_settings
from app.imaging import UnsupportedUpload, store_upload
from app.jobs import reconstruct_board, summarize_lesson
from app.models import Board, JobStatus, Lesson, Role, User
from app.routers.students import own_student
from app.schemas import BoardBrief, LessonIn, LessonOut, LessonUpdate, UserOut
from app.security import DB, CurrentUser, Teacher

router = APIRouter(prefix="/lessons", tags=["lessons"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def image_url(board: Board) -> str | None:
    if board.image_file is None:
        return None
    return f"{get_settings().public_base_url}/files/{board.image_file}"


def board_brief(board: Board) -> BoardBrief:
    return BoardBrief(
        id=board.id,
        position=board.position,
        status=board.status,
        error=board.error,
        image_url=image_url(board),
        width=board.width,
        height=board.height,
        title=(board.scene or {}).get("title"),
    )


def lesson_out(lesson: Lesson) -> LessonOut:
    return LessonOut(
        id=lesson.id,
        title=lesson.title,
        subject=lesson.subject,
        taught_at=lesson.taught_at,
        notes=lesson.notes,
        student=UserOut.model_validate(lesson.student),
        summary=lesson.summary,
        summary_status=lesson.summary_status,
        summary_error=lesson.summary_error,
        boards=[board_brief(b) for b in lesson.boards],
    )


def visible_lesson(db: DB, user: User, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    allowed = lesson is not None and (
        lesson.teacher_id == user.id if user.role == Role.teacher else lesson.student_id == user.id
    )
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    return lesson


def own_lesson(db: DB, teacher: User, lesson_id: int) -> Lesson:
    lesson = visible_lesson(db, teacher, lesson_id)
    if lesson.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    return lesson


@router.get("", response_model=list[LessonOut])
def list_lessons(user: CurrentUser, db: DB, student_id: int | None = None):
    query = select(Lesson).order_by(Lesson.taught_at.desc())
    if user.role == Role.teacher:
        query = query.where(Lesson.teacher_id == user.id)
        if student_id is not None:
            query = query.where(Lesson.student_id == student_id)
    else:
        query = query.where(Lesson.student_id == user.id)
    return [lesson_out(lesson) for lesson in db.scalars(query).all()]


@router.post("", response_model=LessonOut, status_code=201)
def create_lesson(body: LessonIn, teacher: Teacher, db: DB):
    own_student(db, teacher, body.student_id)
    data = body.model_dump(exclude_none=True)
    lesson = Lesson(**data, teacher_id=teacher.id)
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson_out(lesson)


@router.get("/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: int, user: CurrentUser, db: DB):
    return lesson_out(visible_lesson(db, user, lesson_id))


@router.patch("/{lesson_id}", response_model=LessonOut)
def update_lesson(lesson_id: int, body: LessonUpdate, teacher: Teacher, db: DB):
    lesson = own_lesson(db, teacher, lesson_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(lesson, key, value)
    db.commit()
    return lesson_out(lesson)


@router.delete("/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: int, teacher: Teacher, db: DB):
    db.delete(own_lesson(db, teacher, lesson_id))
    db.commit()


@router.post("/{lesson_id}/boards", response_model=list[BoardBrief], status_code=201)
async def upload_boards(
    lesson_id: int, files: list[UploadFile], teacher: Teacher, db: DB, tasks: BackgroundTasks
):
    """Upload screenshots or PDF exports; each image / PDF page becomes a board."""
    lesson = own_lesson(db, teacher, lesson_id)
    position = len(lesson.boards)
    created: list[Board] = []
    for upload in files:
        data = await upload.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"{upload.filename} is too big")
        try:
            images = store_upload(data, upload.content_type or "", upload.filename or "")
        except UnsupportedUpload as exc:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
        for img in images:
            board = Board(
                lesson_id=lesson.id,
                position=position,
                image_file=img.file_name,
                width=img.width,
                height=img.height,
            )
            position += 1
            db.add(board)
            created.append(board)
    db.commit()
    for board in created:
        tasks.add_task(reconstruct_board, board.id)
    return [board_brief(b) for b in created]


@router.post("/{lesson_id}/summarize", response_model=LessonOut, status_code=202)
def request_summary(lesson_id: int, teacher: Teacher, db: DB, tasks: BackgroundTasks):
    lesson = own_lesson(db, teacher, lesson_id)
    if not any(b.status == JobStatus.ready for b in lesson.boards) and not lesson.notes.strip():
        raise HTTPException(status.HTTP_409_CONFLICT, "Nothing to summarize yet")
    lesson.summary_status, lesson.summary_error = JobStatus.pending, None
    db.commit()
    tasks.add_task(summarize_lesson, lesson.id)
    return lesson_out(lesson)
