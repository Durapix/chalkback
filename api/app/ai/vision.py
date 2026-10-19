"""What Claude returns when it reads a board photo or screenshot, and how that becomes a Scene.

The vocabulary follows how the boards were actually used: Miro sticky notes, often in aligned
grids (arrays, matrices); boxes and block arrows moved around to show pointers and references;
connectors between elements; code; handwriting and sketches; pasted documents. Every field is
required so the schema works with structured outputs; "" / [] mean "none".
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.scene import (
    CodeElement,
    ConnectorElement,
    Crop,
    DrawElement,
    FrameElement,
    GeoElement,
    ImageElement,
    MathElement,
    NoteElement,
    Point,
    Scene,
    TextElement,
)


def _kind(value: str):
    # Structured outputs drop `const`; an explicit one-value enum keeps the tag enforced.
    return Field(json_schema_extra={"enum": [value]})


Color = Literal[
    "black", "grey", "blue", "light-blue", "green", "light-green", "red", "light-red",
    "orange", "yellow", "violet", "light-violet",
]  # fmt: skip

ID = Field(description="Short unique id, e.g. 'n1'. Connectors refer to elements by id.")


class VText(BaseModel):
    kind: Literal["text"] = _kind("text")
    id: str = ID
    x: float
    y: float
    w: float
    text: str = Field(description="Exactly as written, same language and script; \\n between lines")
    style: Literal["handwriting", "typed", "code"] = Field(
        description="code: program code or pseudocode, keep indentation with spaces"
    )
    size: Literal["s", "m", "l", "xl"]
    color: Color


class VMath(BaseModel):
    kind: Literal["math"] = _kind("math")
    id: str = ID
    x: float
    y: float
    w: float
    h: float
    latex: str = Field(description="LaTeX without $ delimiters")
    color: Color


class VNote(BaseModel):
    kind: Literal["note"] = _kind("note")
    id: str = ID
    x: float
    y: float
    side: float = Field(description="Width of the square sticky note in pixels")
    text: str
    color: Color


class VCell(BaseModel):
    text: str
    color: Color


class VGrid(BaseModel):
    """Aligned field of equal sticky notes: arrays, matrices, tables, sieves."""

    kind: Literal["grid"] = _kind("grid")
    id: str = Field(description="Cells get ids '<id>:<row>:<col>' (0-based) for connectors")
    x: float = Field(description="Left edge of the top-left cell")
    y: float = Field(description="Top edge of the top-left cell")
    rows: int
    cols: int
    side: float = Field(description="Width of one cell")
    gap_x: float = Field(description="Horizontal space between cells")
    gap_y: float = Field(description="Vertical space between cells")
    cells: list[VCell] = Field(description="rows*cols cells, row by row; empty text if blank")


class VShape(BaseModel):
    kind: Literal["shape"] = _kind("shape")
    id: str = ID
    x: float
    y: float
    w: float
    h: float
    shape: Literal[
        "rectangle", "ellipse", "diamond", "triangle", "trapezoid", "cloud",
        "block-arrow-up", "block-arrow-down", "block-arrow-left", "block-arrow-right",
    ]  # fmt: skip
    filled: bool
    color: Color
    label: str


class VConnector(BaseModel):
    kind: Literal["connector"] = _kind("connector")
    id: str = ID
    from_id: str = Field(description="Element the line starts at, or '' if it starts in space")
    to_id: str = Field(description="Element the line ends at, or '' if it ends in space")
    x1: float
    y1: float
    x2: float
    y2: float
    route: Literal["straight", "elbow", "curved"]
    arrowheads: Literal["end", "start", "both", "none"]
    color: Color
    label: str


class VStroke(BaseModel):
    kind: Literal["stroke"] = _kind("stroke")
    id: str = ID
    points: list[Point] = Field(description="Polyline of a sketch, underline, graph or axis")
    color: Color


class VRegion(BaseModel):
    """Content to keep as a picture: pasted documents, screenshots, dense or complex drawings."""

    kind: Literal["region"] = _kind("region")
    id: str = ID
    x: float
    y: float
    w: float
    h: float
    description: str = Field(description="What the region shows, for search and summaries")


class VFrame(BaseModel):
    """A separate part of a collage (screenshots of different board areas stitched together)."""

    kind: Literal["frame"] = _kind("frame")
    id: str = ID
    x: float
    y: float
    w: float
    h: float
    title: str


VElement = Annotated[
    VText | VMath | VNote | VGrid | VShape | VConnector | VStroke | VRegion | VFrame,
    Field(discriminator="kind"),
]


class VisionScene(BaseModel):
    title: str = Field(description="Short title of the board's topic")
    transcript: str = Field(
        description="Faithful plain-text reading of the whole board, top to bottom, including "
        "code and the text of regions you can read; formulas in LaTeX"
    )
    elements: list[VElement]

    def to_scene(self, factor: float = 1.0) -> Scene:
        """Convert to the board Scene, scaling model-image pixels by `factor`."""
        f = factor
        out: list = []
        frames: list = []
        regions: list = []
        for el in self.elements:
            if isinstance(el, VFrame):
                frames.append(
                    FrameElement(
                        kind="frame",
                        id=el.id,
                        x=el.x * f,
                        y=el.y * f,
                        w=el.w * f,
                        h=el.h * f,
                        name=el.title,
                    )
                )
            elif isinstance(el, VRegion):
                regions.append(
                    ImageElement(
                        kind="image",
                        id=el.id,
                        x=el.x * f,
                        y=el.y * f,
                        w=el.w * f,
                        h=el.h * f,
                        crop=Crop(x=el.x * f, y=el.y * f, w=el.w * f, h=el.h * f),
                        alt=el.description,
                    )
                )
            elif isinstance(el, VText):
                if el.style == "code":
                    out.append(
                        CodeElement(
                            kind="code",
                            id=el.id,
                            x=el.x * f,
                            y=el.y * f,
                            w=el.w * f,
                            text=el.text,
                            color=el.color,
                            scale=f,
                        )
                    )
                else:
                    out.append(
                        TextElement(
                            kind="text",
                            id=el.id,
                            x=el.x * f,
                            y=el.y * f,
                            w=el.w * f,
                            text=el.text,
                            size=el.size,
                            color=el.color,
                            font="draw" if el.style == "handwriting" else "sans",
                            scale=f,
                        )
                    )
            elif isinstance(el, VMath):
                out.append(
                    MathElement(
                        kind="math",
                        id=el.id,
                        x=el.x * f,
                        y=el.y * f,
                        w=el.w * f,
                        h=el.h * f,
                        latex=el.latex,
                        color=el.color,
                    )
                )
            elif isinstance(el, VNote):
                out.append(
                    NoteElement(
                        kind="note",
                        id=el.id,
                        x=el.x * f,
                        y=el.y * f,
                        w=el.side * f,
                        text=el.text,
                        color=el.color,
                    )
                )
            elif isinstance(el, VGrid):
                for i, cell in enumerate(el.cells[: el.rows * el.cols]):
                    r, c = divmod(i, el.cols)
                    out.append(
                        NoteElement(
                            kind="note",
                            id=f"{el.id}:{r}:{c}",
                            x=(el.x + c * (el.side + el.gap_x)) * f,
                            y=(el.y + r * (el.side + el.gap_y)) * f,
                            w=el.side * f,
                            text=cell.text,
                            color=cell.color,
                        )
                    )
            elif isinstance(el, VShape):
                geo = el.shape.removeprefix("block-")
                out.append(
                    GeoElement(
                        kind="geo",
                        id=el.id,
                        x=el.x * f,
                        y=el.y * f,
                        w=el.w * f,
                        h=el.h * f,
                        geo=geo,
                        color=el.color,
                        fill="solid" if el.filled else "none",
                        label=el.label,
                        font="draw",
                        scale=f,
                    )
                )
            elif isinstance(el, VConnector):
                out.append(
                    ConnectorElement(
                        kind="connector",
                        id=el.id,
                        from_id=el.from_id,
                        to_id=el.to_id,
                        x1=el.x1 * f,
                        y1=el.y1 * f,
                        x2=el.x2 * f,
                        y2=el.y2 * f,
                        route=el.route,
                        start_head="arrow" if el.arrowheads in ("start", "both") else "none",
                        end_head="arrow" if el.arrowheads in ("end", "both") else "none",
                        color=el.color,
                        label=el.label,
                        scale=f,
                    )
                )
            elif isinstance(el, VStroke):
                out.append(
                    DrawElement(
                        kind="draw",
                        id=el.id,
                        color=el.color,
                        freehand=True,
                        points=[Point(x=p.x * f, y=p.y * f) for p in el.points],
                    )
                )
        # Frames are backgrounds and regions sit under the transcribed elements.
        return Scene(
            title=self.title,
            transcript=self.transcript,
            source="ai",
            elements=[*frames, *regions, *out],
        )
