"""Background jobs run after the HTTP response (FastAPI BackgroundTasks).

Each job opens its own DB session; failures are recorded on the row, never raised.
"""

import logging

from app.ai.claude import AIError
from app.ai.reconstruct import reconstruct
from app.ai.summarize import summarize
from app.db import SessionLocal
from app.models import Board, JobStatus, Lesson

log = logging.getLogger(__name__)


async def reconstruct_board(board_id: int) -> None:
    with SessionLocal() as db:
        board = db.get(Board, board_id)
        if board is None or board.image_file is None:
            return
        board.status, board.error = JobStatus.processing, None
        db.commit()
        try:
            scene = await reconstruct(board.image_file)
        except AIError as exc:
            board.status, board.error = JobStatus.failed, str(exc)
        except Exception:
            log.exception("Reconstruction of board %s failed", board_id)
            board.status, board.error = JobStatus.failed, "Unexpected error during reconstruction"
        else:
            board.scene = scene.model_dump()
            board.snapshot = None  # rebuilt from the new scene on next open
            board.status = JobStatus.ready
        db.commit()


async def summarize_lesson(lesson_id: int) -> None:
    with SessionLocal() as db:
        lesson = db.get(Lesson, lesson_id)
        if lesson is None:
            return
        lesson.summary_status, lesson.summary_error = JobStatus.processing, None
        db.commit()
        student = lesson.student
        try:
            summary = await summarize(lesson, student.name.split()[0], student.language)
        except AIError as exc:
            lesson.summary_status, lesson.summary_error = JobStatus.failed, str(exc)
        except Exception:
            log.exception("Summary of lesson %s failed", lesson_id)
            lesson.summary_status = JobStatus.failed
            lesson.summary_error = "Unexpected error while summarizing"
        else:
            # The language it was written in, for the section titles around it.
            lesson.summary = {**summary.model_dump(), "language": student.language}
            lesson.summary_status = JobStatus.ready
        db.commit()
