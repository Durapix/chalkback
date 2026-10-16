"""Turning uploads (images, PDFs) into normalized PNG board images."""

import base64
import io
import secrets
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from app.config import get_settings

MAX_BOARD_EDGE = 4000  # stored image cap
MAX_MODEL_EDGE = 1568  # long edge sent to the vision model
PDF_RENDER_SCALE = 2.0  # 144 dpi
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
PDF_TYPES = {"application/pdf"}


class UnsupportedUpload(ValueError):
    pass


@dataclass
class StoredImage:
    file_name: str
    width: int
    height: int


def _save(img: Image.Image) -> StoredImage:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_BOARD_EDGE, MAX_BOARD_EDGE))
    uploads = get_settings().uploads_dir
    uploads.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_urlsafe(24)}.png"
    img.save(uploads / name, format="PNG", optimize=True)
    return StoredImage(name, img.width, img.height)


def store_upload(data: bytes, content_type: str, filename: str = "") -> list[StoredImage]:
    """Store an upload as one PNG per board (PDFs produce one board per page)."""
    is_pdf = content_type in PDF_TYPES or filename.lower().endswith(".pdf")
    if is_pdf:
        try:
            pdf = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as exc:
            raise UnsupportedUpload("Could not read PDF") from exc
        try:
            return [_save(page.render(scale=PDF_RENDER_SCALE).to_pil()) for page in pdf]
        finally:
            pdf.close()
    if content_type not in IMAGE_TYPES:
        raise UnsupportedUpload(f"Unsupported file type: {content_type}")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise UnsupportedUpload("Could not read image") from exc
    return [_save(img)]


def image_path(file_name: str) -> Path:
    return get_settings().uploads_dir / file_name


def model_image(file_name: str) -> tuple[str, int, int, float]:
    """Base64 PNG sized for the vision model, its size, and the factor back to full size."""
    img = Image.open(image_path(file_name))
    full_w = img.width
    img.thumbnail((MAX_MODEL_EDGE, MAX_MODEL_EDGE))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    factor = full_w / img.width
    return base64.standard_b64encode(buf.getvalue()).decode(), img.width, img.height, factor
