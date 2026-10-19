"""Turn uploaded files into boards, and keep track of the files boards own.

- Images and PDFs become boards that still need AI reconstruction.
- draw.io exports are imported exactly and are ready immediately.
"""

from dataclasses import dataclass, field

from app.imaging import (
    read_source_file,
    remove_images,
    remove_source_files,
    store_source_file,
    store_upload,
)
from app.importers.drawio import DrawioError, import_drawio, looks_like_drawio
from app.models import Board, JobStatus


class IngestError(ValueError):
    pass


@dataclass
class Ingested:
    boards: list[Board] = field(default_factory=list)
    upload_files: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def discard(self) -> None:
        """Remove every file written for this upload (used when the request fails)."""
        remove_images(self.upload_files)
        remove_source_files(self.source_files)


def ingest(data: bytes, content_type: str, filename: str, into: Ingested) -> None:
    """Add the boards for one uploaded file to `into` (files are recorded as they are written)."""
    if looks_like_drawio(data, filename, content_type):
        try:
            pages = import_drawio(data)
        except DrawioError as exc:
            raise IngestError(f"{filename}: {exc}") from exc
        source = store_source_file(data)
        into.source_files.append(source)
        for index, page in enumerate(pages):
            into.upload_files += page.files
            into.boards.append(
                Board(
                    width=page.width,
                    height=page.height,
                    scene=page.scene.model_dump(),
                    status=JobStatus.ready,
                    source_file=source,
                    source_page=index,
                )
            )
        return
    for img in store_upload(data, content_type, filename):
        into.upload_files.append(img.file_name)
        into.boards.append(Board(image_file=img.file_name, width=img.width, height=img.height))


def scene_files(scene: dict | None) -> list[str]:
    """Upload files referenced by a scene (embedded images)."""
    return [el["file"] for el in (scene or {}).get("elements", []) if el.get("file")]


def reimport(board: Board) -> list[str]:
    """Rebuild an imported board from its stored source. Returns files it no longer uses."""
    pages = import_drawio(read_source_file(board.source_file))
    if board.source_page >= len(pages):
        raise IngestError("The source document no longer has this page")
    old = scene_files(board.scene)
    page = pages[board.source_page]
    # Images of the other pages were extracted again; only this page's are kept.
    remove_images(f for i, p in enumerate(pages) if i != board.source_page for f in p.files)
    board.scene = page.scene.model_dump()
    board.width, board.height = page.width, page.height
    board.snapshot = None
    board.status, board.error = JobStatus.ready, None
    return old


def owned_files(boards: list[Board], keep: list[Board]) -> tuple[list[str], list[str]]:
    """(upload files, source files) of `boards` that no board in `keep` still uses."""
    uploads = [f for b in boards for f in [b.image_file, *scene_files(b.scene)] if f]
    still_used = {b.source_file for b in keep if b.source_file}
    sources = list({b.source_file for b in boards if b.source_file} - still_used)
    return uploads, sources
