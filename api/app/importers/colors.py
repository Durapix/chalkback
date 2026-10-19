"""Map arbitrary CSS hex colors onto tldraw's fixed palette."""

import colorsys

from app.scene import Color, Fill


def parse_hex(value: str | None) -> tuple[float, float, float] | None:
    """'#rgb' / '#rrggbb' -> (r, g, b) in 0..1; None for 'none', 'default' and junk."""
    if not value or not value.startswith("#"):
        return None
    h = value[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def to_palette(value: str | None, default: Color = "black") -> Color:
    rgb = parse_hex(value)
    if rgb is None:
        return default
    hue, light, sat = colorsys.rgb_to_hls(*rgb)
    deg = hue * 360
    if sat < 0.15 or light > 0.97:
        if light > 0.9:
            return "white" if light > 0.97 else "grey"
        return "black" if light < 0.35 else "grey"
    pale = light > 0.72
    if deg < 15 or deg >= 345:
        return "light-red" if pale else "red"
    if deg < 45:
        return "orange"
    if deg < 70:
        return "yellow"
    if deg < 165:
        return "light-green" if pale else "green"
    if deg < 200:
        return "light-blue"
    if deg < 250:
        return "light-blue" if pale else "blue"
    if deg < 290:
        return "light-violet" if pale else "violet"
    return "light-red" if pale else "violet"


def fill_style(value: str | None, default_white: bool) -> Fill:
    """How strongly a shape is filled: none, white (semi), pastel (solid) or saturated (fill)."""
    if value == "none":
        return "none"
    rgb = parse_hex(value)
    if rgb is None:
        return "semi" if default_white else "none"
    _, light, sat = colorsys.rgb_to_hls(*rgb)
    if light > 0.97 or sat < 0.1 and light > 0.9:
        return "semi"
    return "solid" if light > 0.72 else "fill"
