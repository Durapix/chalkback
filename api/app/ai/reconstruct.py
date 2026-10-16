from app.ai.claude import structured_call
from app.ai.scene import Scene
from app.config import get_settings
from app.imaging import model_image

SYSTEM = """You digitize photos and screenshots of tutoring whiteboards into a structured \
scene that will be rebuilt as an editable digital whiteboard, drawn on top of the original \
image.

Describe every meaningful mark on the board as an element:
- `text` for handwritten or typed words and short labels;
- `math` for any formula, equation or expression, as LaTeX;
- `geo` for boxes, circles and other closed shapes;
- `arrow` for arrows and pointers;
- `draw` for everything else: graphs, axes, curves, underlines, sketches (a polyline of \
points is fine).

Coordinates are pixels in the image as you receive it, origin top-left. Place each element \
where it appears so it lines up with the original. Transcribe text exactly as written, \
including the original language and any mistakes; do not translate or correct. Ignore UI \
chrome around the board (toolbars, cursors, window frames)."""


async def reconstruct(file_name: str) -> Scene:
    if not get_settings().ai_enabled:
        return mock_scene(file_name)

    data, width, height, factor = model_image(file_name)
    scene = await structured_call(
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
        output=Scene,
        effort=get_settings().reconstruct_effort,
    )
    return scene.scaled(factor)


def mock_scene(file_name: str | None, width: int = 1600, height: int = 900) -> Scene:
    """Deterministic stand-in used when no API key is configured (dev, tests, demo)."""
    if file_name:
        _, w, h, factor = model_image(file_name)
        width, height = round(w * factor), round(h * factor)
    return Scene.model_validate(
        {
            "title": "Quadratic equations",
            "transcript": "Quadratic equations\nax^2 + bx + c = 0\n"
            "D = b^2 - 4ac\nx_{1,2} = \\frac{-b \\pm \\sqrt{D}}{2a}\n"
            "D > 0: two real roots",
            "elements": [
                {
                    "kind": "text",
                    "x": width * 0.06,
                    "y": height * 0.06,
                    "w": width * 0.5,
                    "text": "Quadratic equations",
                    "size": "xl",
                    "color": "black",
                },
                {
                    "kind": "math",
                    "x": width * 0.08,
                    "y": height * 0.22,
                    "w": width * 0.3,
                    "h": height * 0.08,
                    "latex": "ax^2 + bx + c = 0",
                    "color": "blue",
                },
                {
                    "kind": "math",
                    "x": width * 0.08,
                    "y": height * 0.38,
                    "w": width * 0.25,
                    "h": height * 0.08,
                    "latex": "D = b^2 - 4ac",
                    "color": "black",
                },
                {
                    "kind": "geo",
                    "x": width * 0.06,
                    "y": height * 0.54,
                    "w": width * 0.4,
                    "h": height * 0.16,
                    "geo": "rectangle",
                    "color": "red",
                    "label": "",
                },
                {
                    "kind": "math",
                    "x": width * 0.08,
                    "y": height * 0.57,
                    "w": width * 0.36,
                    "h": height * 0.1,
                    "latex": "x_{1,2} = \\frac{-b \\pm \\sqrt{D}}{2a}",
                    "color": "black",
                },
                {
                    "kind": "arrow",
                    "x1": width * 0.48,
                    "y1": height * 0.42,
                    "x2": width * 0.6,
                    "y2": height * 0.42,
                    "color": "green",
                    "label": "",
                },
                {
                    "kind": "text",
                    "x": width * 0.62,
                    "y": height * 0.39,
                    "w": width * 0.3,
                    "text": "D > 0: two real roots",
                    "size": "m",
                    "color": "green",
                },
                {
                    "kind": "draw",
                    "color": "violet",
                    "points": [
                        {
                            "x": width * (0.6 + i * 0.03),
                            "y": height * (0.85 - 0.6 * ((i - 5) / 5) ** 2 * 0.5),
                        }
                        for i in range(11)
                    ],
                },
            ],
        }
    )
