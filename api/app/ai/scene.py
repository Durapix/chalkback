"""The scene format Claude produces when it reads a whiteboard.

Deliberately much simpler than tldraw's own record format: the model only has to describe
*what* is on the board and *where*; the web app turns each element into real tldraw shapes.
All coordinates are in pixels of the original board image, origin top-left.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


def _kind(value: str):
    # Structured outputs drop `const`; an explicit one-value enum keeps the tag enforced.
    return Field(json_schema_extra={"enum": [value]})


Color = Literal["black", "grey", "blue", "light-blue", "green", "red", "orange", "violet"]


class Point(BaseModel):
    x: float
    y: float


class TextElement(BaseModel):
    kind: Literal["text"] = _kind("text")
    x: float
    y: float
    w: float = Field(description="Approximate width of the text block in pixels")
    text: str = Field(description="Exact text as written, plain text without LaTeX")
    size: Literal["s", "m", "l", "xl"]
    color: Color


class MathElement(BaseModel):
    kind: Literal["math"] = _kind("math")
    x: float
    y: float
    w: float
    h: float
    latex: str = Field(description="The formula as LaTeX, without surrounding $ delimiters")
    color: Color


class GeoElement(BaseModel):
    kind: Literal["geo"] = _kind("geo")
    x: float
    y: float
    w: float
    h: float
    geo: Literal["rectangle", "ellipse", "triangle", "diamond"]
    color: Color
    label: str = Field(description="Text inside the shape, or empty string")


class ArrowElement(BaseModel):
    kind: Literal["arrow"] = _kind("arrow")
    x1: float
    y1: float
    x2: float
    y2: float
    color: Color
    label: str = Field(description="Text on the arrow, or empty string")


class DrawElement(BaseModel):
    kind: Literal["draw"] = _kind("draw")
    points: list[Point] = Field(
        description="Polyline approximating a freehand stroke, curve, graph or axis"
    )
    color: Color


Element = Annotated[
    TextElement | MathElement | GeoElement | ArrowElement | DrawElement,
    Field(discriminator="kind"),
]


class Scene(BaseModel):
    title: str = Field(description="Short title describing the board's topic")
    transcript: str = Field(
        description="Faithful plain-text reading of everything on the board, top to bottom, "
        "with formulas in LaTeX"
    )
    elements: list[Element]

    def scaled(self, factor: float) -> "Scene":
        """Return a copy with every coordinate multiplied by `factor`."""
        if factor == 1:
            return self.model_copy(deep=True)
        data = self.model_dump()
        for el in data["elements"]:
            for key in ("x", "y", "w", "h", "x1", "y1", "x2", "y2"):
                if key in el:
                    el[key] = round(el[key] * factor, 1)
            for p in el.get("points", []):
                p["x"] = round(p["x"] * factor, 1)
                p["y"] = round(p["y"] * factor, 1)
        return Scene.model_validate(data)


class LessonSummary(BaseModel):
    headline: str = Field(description="One-line summary of the lesson")
    topics: list[str]
    key_points: list[str] = Field(description="The most important ideas, one sentence each")
    formulas: list[str] = Field(description="Key formulas in LaTeX, no $ delimiters")
    exercises: list[str] = Field(description="Exercises that were solved, briefly")
    recap_message: str = Field(
        description="A warm 2-4 sentence message to the student reminding them what was "
        "covered, written directly to them"
    )
    review_suggestions: list[str] = Field(description="What to practise before next lesson")
