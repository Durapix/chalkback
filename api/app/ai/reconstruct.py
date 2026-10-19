from app.ai.claude import structured_call
from app.ai.vision import VisionScene
from app.config import get_settings
from app.imaging import model_image
from app.scene import Scene

SYSTEM = """You turn photos and screenshots of tutoring whiteboards into a structured scene. \
The scene is rebuilt as an editable digital whiteboard laid over the original image, and the \
tutor will keep working on it: moving sticky notes, recoloring them, re-pointing arrows. So \
capture each thing as the element a tutor would want to grab and move.

The boards come from lessons on programming and algorithms, mathematics, electronics and \
databases, mostly in Serbian (Cyrillic or Latin script). Screenshots are often collages of \
several board areas stitched together.

Elements:
- `grid`: an aligned field of equal sticky notes (arrays, matrices, indexes, a sieve of \
numbers). Use one grid instead of many notes whenever notes line up in rows and columns; \
give every cell its text and color.
- `note`: a single sticky note (a square with text) that is not part of an aligned field.
- `shape`: boxes, circles, diamonds and other outlined or filled shapes. Use the \
`block-arrow-*` shapes for big hollow arrows that point at something (pointers, indexes \
such as L, D, S).
- `connector`: a line or arrow between two places. When it starts or ends at an element, \
set `from_id` / `to_id` to that element's id (a grid cell is '<grid id>:<row>:<col>'). Use \
route `curved` for smooth curves, `elbow` for lines with right-angle bends, `straight` \
otherwise; `arrowheads` says which ends have an arrowhead.
- `text`: words and sentences. `style` is `code` for program code or pseudocode (keep \
indentation with spaces), `handwriting` for handwriting, `typed` otherwise.
- `math`: formulas and equations as LaTeX.
- `stroke`: sketches, underlines, check marks, graphs and axes, as a polyline.
- `region`: content better kept as a picture of the original: pasted documents and task \
statements, screenshots of other programs, tables of small print, dense handwritten \
derivations, complex drawings. Still put the readable text of a region in the transcript.
- `frame`: each separate part of a collage, with a short title.

Coordinates are pixels in the image as you receive it, origin top-left; place everything \
where it appears. Transcribe text exactly as written, in its language and script, mistakes \
included; never translate or correct. Pick the nearest palette color. Ignore app chrome \
(toolbars, cursors, zoom controls, share buttons)."""


async def reconstruct(file_name: str) -> Scene:
    if not get_settings().ai_enabled:
        return mock_scene(file_name)

    data, width, height, factor = model_image(file_name)
    vision = await structured_call(
        system=SYSTEM,
        content=[
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": data},
            },
            {
                "type": "text",
                "text": f"This board image is {width}x{height} pixels. Reconstruct it.",
            },
        ],
        output=VisionScene,
        effort=get_settings().reconstruct_effort,
    )
    return vision.to_scene(factor)


MOCK_W, MOCK_H = 1600, 900


def mock_scene(file_name: str | None) -> Scene:
    """Deterministic stand-in used without an API key (dev, tests, demo).

    It mirrors a real lesson board (binary search over a sticky-note array) so every element
    kind goes through the same conversion as real AI output.
    """
    width = MOCK_W
    if file_name:
        _, w, _, factor = model_image(file_name)
        width = round(w * factor)
    values = list(range(0, 31, 2))
    side, gap, x0, y0 = 52, 14, 120, 420
    cell_x = [x0 + i * (side + gap) for i in range(len(values))]
    elements: list[dict] = [
        {
            "kind": "frame",
            "id": "f1",
            "x": 60,
            "y": 40,
            "w": 1480,
            "h": 820,
            "title": "Binary search",
        },
        {
            "kind": "text",
            "id": "t1",
            "x": 120,
            "y": 90,
            "w": 620,
            "style": "typed",
            "size": "l",
            "color": "black",
            "text": "search(array, 0, 15, 10)",
        },
        {
            "kind": "text",
            "id": "c1",
            "x": 980,
            "y": 90,
            "w": 520,
            "style": "code",
            "size": "m",
            "color": "black",
            "text": "L = 0\nD = 15\nS = (L + D) / 2\nif array[S] == x: return S\n"
            "if x < array[S]:\n    search(array, L, S - 1)\nelse:\n"
            "    search(array, S + 1, D)",
        },
        {
            "kind": "grid",
            "id": "g1",
            "x": x0,
            "y": y0,
            "rows": 1,
            "cols": len(values),
            "side": side,
            "gap_x": gap,
            "gap_y": 0,
            "cells": [{"text": str(v), "color": "yellow"} for v in values],
        },
        {
            "kind": "shape",
            "id": "L",
            "x": cell_x[0] - 4,
            "y": y0 + 90,
            "w": 60,
            "h": 130,
            "shape": "block-arrow-up",
            "filled": False,
            "color": "grey",
            "label": "L",
        },
        {
            "kind": "shape",
            "id": "D",
            "x": cell_x[-1] - 4,
            "y": y0 + 90,
            "w": 60,
            "h": 130,
            "shape": "block-arrow-up",
            "filled": False,
            "color": "grey",
            "label": "D",
        },
        {
            "kind": "shape",
            "id": "S",
            "x": cell_x[7] - 14,
            "y": y0 - 190,
            "w": 80,
            "h": 150,
            "shape": "block-arrow-down",
            "filled": False,
            "color": "grey",
            "label": "S",
        },
        {
            "kind": "note",
            "id": "n1",
            "x": cell_x[7],
            "y": y0 + 190,
            "side": side,
            "text": "10",
            "color": "orange",
        },
        {
            "kind": "connector",
            "id": "k1",
            "from_id": "n1",
            "to_id": "g1:0:5",
            "x1": cell_x[7] + side / 2,
            "y1": y0 + 190,
            "x2": cell_x[5] + side / 2,
            "y2": y0 + side,
            "route": "curved",
            "arrowheads": "none",
            "color": "violet",
            "label": "",
        },
        {
            "kind": "stroke",
            "id": "s1",
            "color": "green",
            "points": [{"x": 820, "y": 150}, {"x": 845, "y": 185}, {"x": 900, "y": 95}],
        },
        {
            "kind": "math",
            "id": "m1",
            "x": 980,
            "y": 330,
            "w": 300,
            "h": 50,
            "latex": "S = \\left\\lfloor \\frac{L + D}{2} \\right\\rfloor",
            "color": "blue",
        },
    ]
    vision = VisionScene.model_validate(
        {
            "title": "Binary search",
            "transcript": "search(array, 0, 15, 10)\nL = 0, D = 15, S = (L + D) / 2\n"
            "Array: " + ", ".join(map(str, values)) + "\nLooking for 10.",
            "elements": elements,
        }
    )
    scene = vision.to_scene(width / MOCK_W)
    scene.source = "mock"
    return scene
