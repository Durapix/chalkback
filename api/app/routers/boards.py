from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.imaging import remove_images, remove_source_files
from app.importers.drawio import DrawioError
from app.ingest import IngestError, owned_files, reimport, scene_files
from app.jobs import reconstruct_board
from app.models import Board, JobStatus, User
from app.routers.lessons import board_brief, own_lesson, visible_lesson
from app.scene import Scene
from app.schemas import BoardOut, SnapshotIn
from app.security import DB, CurrentUser, Teacher

router = APIRouter(prefix="/boards", tags=["boards"])


def visible_board(db: DB, user: User, board_id: int) -> Board:
    board = db.get(Board, board_id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Board not found")
    visible_lesson(db, user, board.lesson_id)
    return board


def board_out(board: Board) -> BoardOut:
    return BoardOut(
        **board_brief(board).model_dump(),
        lesson_id=board.lesson_id,
        # Normalized so scenes stored by older versions get today's defaults.
        scene=Scene.model_validate(board.scene).model_dump() if board.scene else None,
        snapshot=board.snapshot,
        updated_at=board.updated_at,
    )


@router.get("/{board_id}", response_model=BoardOut)
def get_board(board_id: int, user: CurrentUser, db: DB):
    return board_out(visible_board(db, user, board_id))


@router.put("/{board_id}/snapshot", response_model=BoardOut)
def save_snapshot(board_id: int, body: SnapshotIn, user: CurrentUser, db: DB):
    """Persist the tldraw store snapshot after the board was edited in the app."""
    board = visible_board(db, user, board_id)
    board.snapshot = body.snapshot
    db.commit()
    return board_out(board)


@router.post("/{board_id}/reconstruct", response_model=BoardOut, status_code=202)
def rerun_reconstruction(board_id: int, teacher: Teacher, db: DB, tasks: BackgroundTasks):
    """Rebuild a board: imported boards are re-imported at once, photos go back to the AI."""
    board = visible_board(db, teacher, board_id)
    own_lesson(db, teacher, board.lesson_id)
    if board.source_file:
        try:
            stale = reimport(board)
        except (DrawioError, IngestError, OSError) as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Re-import failed: {exc}") from exc
        db.commit()
        remove_images(f for f in stale if f not in scene_files(board.scene))
        return board_out(board)
    if board.image_file is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Board has no source image")
    board.status, board.error = JobStatus.pending, None
    db.commit()
    tasks.add_task(reconstruct_board, board.id)
    return board_out(board)


@router.delete("/{board_id}", status_code=204)
def delete_board(board_id: int, teacher: Teacher, db: DB):
    board = visible_board(db, teacher, board_id)
    lesson = own_lesson(db, teacher, board.lesson_id)
    uploads, sources = owned_files([board], keep=[b for b in lesson.boards if b.id != board.id])
    db.delete(board)
    db.commit()
    remove_images(uploads)
    remove_source_files(sources)
