"""The board scene: what the web app turns into tldraw shapes.

Scenes come from two places:
- the draw.io importer (exact geometry, styles and connections), and
- the AI reconstruction of photos and screenshots (see app.ai.vision).

All coordinates and sizes are board pixels, origin top-left (for photos: pixels of the original
image). `scale` only enlarges text, labels and strokes; the web app accounts for it.

Elements are drawn in list order, so containers come before their contents. `id` values let
connectors attach to elements; an attached connector follows its element when the element is
moved in the app.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# tldraw's palette. Importers map arbitrary colors onto it.
Color = Literal[
    "black", "grey", "light-violet", "violet", "blue", "light-blue", "yellow",
    "orange", "green", "light-green", "light-red", "red", "white",
]  # fmt: skip
Font = Literal["draw", "sans", "serif", "mono"]
Size = Literal["s", "m", "l", "xl"]
Align = Literal["start", "middle", "end"]
Fill = Literal["none", "semi", "solid", "fill"]
Dash = Literal["solid", "dashed", "dotted", "draw"]
GeoKind = Literal[
    "rectangle", "ellipse", "triangle", "diamond", "trapezoid", "hexagon", "cloud",
    "star", "oval", "rhombus", "arrow-up", "arrow-down", "arrow-left", "arrow-right",
]  # fmt: skip
Arrowhead = Literal["none", "arrow", "triangle", "dot", "diamond"]


class Point(BaseModel):
    x: float
    y: float


class Base(BaseModel):
    id: str = ""
    rotation: float = 0  # degrees, clockwise, around the element's center
    opacity: float = 1  # e.g. faded steps that are "not active yet"


class TextElement(Base):
    kind: Literal["text"]
    x: float
    y: float
    w: float
    h: float = 0
    text: str
    size: Size = "m"
    color: Color = "black"
    font: Font = "draw"
    align: Align = "start"
    wrap: bool = True
    scale: float = 1


class MathElement(Base):
    kind: Literal["math"]
    x: float
    y: float
    w: float
    h: float
    latex: str
    color: Color = "black"


class GeoElement(Base):
    kind: Literal["geo"]
    x: float
    y: float
    w: float
    h: float
    geo: GeoKind = "rectangle"
    color: Color = "black"
    fill: Fill = "none"
    dash: Dash = "solid"
    label: str = ""
    label_color: Color | None = None
    font: Font = "draw"
    size: Size = "m"
    align: Align = "middle"
    valign: Align = "middle"
    scale: float = 1
    flip_y: bool = False  # outline mirrored vertically (label stays upright)


class NoteElement(Base):
    """A sticky note (Miro sticker). Square in tldraw; scaled to `w`."""

    kind: Literal["note"]
    x: float
    y: float
    w: float
    text: str = ""
    color: Color = "yellow"
    font: Font = "sans"


class CodeElement(Base):
    kind: Literal["code"]
    x: float
    y: float
    w: float
    text: str
    color: Color = "black"
    scale: float = 1


class Anchor(BaseModel):
    """Where a connector touches an element, normalized to its box (0..1)."""

    x: float
    y: float


class ConnectorElement(Base):
    """An arrow or plain line. Attached ends (`from_id`/`to_id`) follow their element."""

    kind: Literal["connector", "arrow"]  # "arrow": scenes stored before connectors existed
    x1: float
    y1: float
    x2: float
    y2: float
    from_id: str = ""
    to_id: str = ""
    from_anchor: Anchor | None = None
    to_anchor: Anchor | None = None
    route: Literal["straight", "elbow", "curved"] = "straight"
    bend: float = 0  # curved route: sideways offset of the midpoint, in pixels
    start_head: Arrowhead = "none"
    end_head: Arrowhead = "arrow"
    color: Color = "black"
    dash: Dash = "solid"
    label: str = ""
    scale: float = 1


class DrawElement(Base):
    """A stroke: freehand pen ink, or a smooth polyline (graphs, curves, axes)."""

    kind: Literal["draw"]
    points: list[Point]
    color: Color = "black"
    freehand: bool = False
    closed: bool = False
    filled: bool = False  # closed outline filled with the color (draw.io pen ink)
    smooth: bool = True  # False: straight segments between points (wires, polylines)
    size: Size = "s"


class Crop(BaseModel):
    """Part of the board's original image, in original-image pixels."""

    x: float
    y: float
    w: float
    h: float


class ImageElement(Base):
    """An embedded picture (`file`, stored in uploads) or a cut-out of the original (`crop`)."""

    kind: Literal["image"]
    x: float
    y: float
    w: float
    h: float
    file: str = ""
    crop: Crop | None = None
    alt: str = ""


class FrameElement(Base):
    """A titled section, e.g. one screenshot in a collage of board parts."""

    kind: Literal["frame"]
    x: float
    y: float
    w: float
    h: float
    name: str = ""


Element = Annotated[
    TextElement
    | MathElement
    | GeoElement
    | NoteElement
    | CodeElement
    | ConnectorElement
    | DrawElement
    | ImageElement
    | FrameElement,
    Field(discriminator="kind"),
]


class Scene(BaseModel):
    title: str = ""
    transcript: str = ""
    source: Literal["ai", "drawio", "mock"] = "ai"
    elements: list[Element] = []

    def bounds(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) over all elements; zeros for an empty scene."""
        xs: list[float] = []
        ys: list[float] = []
        for el in self.elements:
            if isinstance(el, ConnectorElement):
                xs += [el.x1, el.x2]
                ys += [el.y1, el.y2]
            elif isinstance(el, DrawElement):
                xs += [p.x for p in el.points]
                ys += [p.y for p in el.points]
            else:
                w = getattr(el, "w", 0)
                h = getattr(el, "h", 0) or (w if isinstance(el, NoteElement) else 0)
                xs += [el.x, el.x + w]
                ys += [el.y, el.y + h]
        if not xs:
            return 0, 0, 0, 0
        return min(xs), min(ys), max(xs), max(ys)

    def translated(self, dx: float, dy: float) -> "Scene":
        data = self.model_dump()
        for el in data["elements"]:
            for key in ("x", "x1", "x2"):
                if key in el:
                    el[key] += dx
            for key in ("y", "y1", "y2"):
                if key in el:
                    el[key] += dy
            for p in el.get("points", []):
                p["x"] += dx
                p["y"] += dy
        return Scene.model_validate(data)

    def scaled(self, factor: float) -> "Scene":
        """Multiply every coordinate and size by `factor`."""
        if factor == 1:
            return self.model_copy(deep=True)
        data = self.model_dump()
        for el in data["elements"]:
            for key in ("x", "y", "w", "h", "x1", "y1", "x2", "y2", "bend"):
                if key in el:
                    el[key] = round(el[key] * factor, 1)
            for p in el.get("points", []):
                p["x"] = round(p["x"] * factor, 1)
                p["y"] = round(p["y"] * factor, 1)
            if "scale" in el:
                el["scale"] = round(el["scale"] * factor, 3)
            if el.get("crop"):
                el["crop"] = {k: round(v * factor, 1) for k, v in el["crop"].items()}
        return Scene.model_validate(data)


TLDRAW_S_FONT_PX = 18  # font size of tldraw size "s"; text `scale` is relative to it


def fit_text_scale(width: float, text: str, mono: bool = False) -> float:
    """Text scale that makes the longest line about `width` pixels wide.

    Used for AI-read text, where we know a block's width and its lines but not its font size.
    """
    longest = max((len(line) for line in text.splitlines()), default=0) or 1
    char_w = 0.6 if mono else 0.52  # average glyph width / font size
    font_px = width / (longest * char_w)
    return round(max(0.4, min(font_px / TLDRAW_S_FONT_PX, 6.0)), 3)


LABEL_PAD = 16  # tldraw's padding around shape labels, in label-scale units


def fit_wrapped_label_scale(w: float, h: float, text: str, max_scale: float) -> float:
    """Largest label scale <= max_scale whose word-wrapped text fits a w x h shape.

    tldraw grows a shape that is too short for its label; on boards where shapes border each
    other (tables, joined steps, circuits) that would make them overlap.
    """
    paragraphs = [p for p in text.splitlines() if p.strip()] or [""]
    scale = max_scale
    while scale > 0.15:
        avail = w - 2 * LABEL_PAD * scale
        char_px = 0.55 * TLDRAW_S_FONT_PX * scale
        if avail > char_px:
            per_line = max(1, int(avail // char_px))
            lines = sum(max(1, -(-len(p) // per_line)) for p in paragraphs)
            height = lines * 1.35 * TLDRAW_S_FONT_PX * scale + 2 * LABEL_PAD * scale
            if height <= h:
                return round(scale, 3)
        scale *= 0.92
    return round(scale, 3)


def fit_label_scale(w: float, h: float, text: str) -> float:
    """Label scale that fits `text` (no wrapping inside words) into a w x h shape."""
    lines = text.splitlines() or [""]
    longest = max((len(line) for line in lines), default=0) or 1
    by_width = w / (longest * 0.62 * TLDRAW_S_FONT_PX + 2 * LABEL_PAD)
    by_height = h / (len(lines) * 1.35 * TLDRAW_S_FONT_PX + 2 * LABEL_PAD)
    return round(max(0.05, 0.95 * min(by_width, by_height, 4.0)), 3)


MARK_COLORS = {"red": "red", "light-red": "red", "green": "green", "light-green": "green"}


def reading_order_text(
    scene: Scene, skip_ids: set[str] = frozenset(), skip_texts: set[str] = frozenset()
) -> str:
    """Plain-text reading of a scene (top-to-bottom, left-to-right) for summaries.

    Elements in `skip_ids` and texts equal to one of `skip_texts` are left out (e.g. parts
    already described as a flowchart).
    """
    labelled: list[tuple[float, float, str]] = []
    names = {}
    for el in scene.elements:
        text, mark = "", None
        if isinstance(el, TextElement | NoteElement | CodeElement):
            text = el.text
        elif isinstance(el, GeoElement):
            text = el.label
            # Cells colored red or green usually mark rows ruled out / kept (e.g. a query
            # filtering a table step by step).
            mark = MARK_COLORS.get(el.color) if el.fill in ("solid", "fill") else None
        elif isinstance(el, MathElement):
            text = f"${el.latex}$"
        elif isinstance(el, FrameElement):
            text = f"[{el.name}]" if el.name else ""
        if not text.strip():
            continue
        if el.id:
            names[el.id] = " ".join(text.split())[:40]
        if not (el.id in skip_ids or " ".join(text.split()) in skip_texts):
            labelled.append((el.y, el.x, text.strip() + (f" ({mark})" if mark else "")))
    # Group into rows of roughly the same height so side-by-side items read left to right.
    labelled.sort()
    lines, row, row_y = [], [], None
    for y, x, text in labelled:
        if row_y is not None and y - row_y > 12:
            lines.append("  |  ".join(t for _, t in sorted(row)))
            row = []
        if not row:
            row_y = y
        row.append((x, text))
    if row:
        lines.append("  |  ".join(t for _, t in sorted(row)))
    links = [
        f"{names[el.from_id]} -> {names[el.to_id]}" + (f" ({el.label})" if el.label else "")
        for el in scene.elements
        if isinstance(el, ConnectorElement)
        and el.from_id in names
        and el.to_id in names
        # Arrows inside an already described flowchart are not repeated.
        and not (el.from_id in skip_ids and el.to_id in skip_ids)
    ]
    if links:
        lines += ["", "Connections:", *links]
    return "\n".join(lines)
