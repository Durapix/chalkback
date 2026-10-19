"""Import draw.io / diagrams.net boards exactly, without AI.

Accepts the three forms draw.io produces:
- an HTML export (the diagram XML sits in a `data-mxgraph` attribute),
- a `.drawio` / `.xml` file (`<mxfile>` with one `<diagram>` per page), and
- a bare `<mxGraphModel>`.
Page contents may be plain XML or draw.io's compressed form (raw deflate + base64 + URL encoding).

Each page becomes one Scene: shapes keep their geometry, colors and labels; connectors keep
which shapes they attach to; pen strokes stay pen strokes; embedded images are extracted to
the uploads folder.
"""

import base64
import binascii
import html
import json
import math
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field

from app.flowchart import board_reading
from app.importers.colors import fill_style, to_palette
from app.scene import (
    Anchor,
    Arrowhead,
    ConnectorElement,
    DrawElement,
    GeoElement,
    GeoKind,
    ImageElement,
    Point,
    Scene,
    TextElement,
    fit_wrapped_label_scale,  # noqa: I001
)

MARGIN = 40
DEFAULT_FONT_PX = 12  # draw.io default
TLDRAW_S_FONT_PX = 18  # tldraw font size for size "s"
MAX_IMAGE_BYTES = 15 * 1024 * 1024


class DrawioError(ValueError):
    pass


@dataclass
class ImportedPage:
    name: str
    scene: Scene
    width: int
    height: int
    files: list[str] = field(default_factory=list)  # embedded images written to uploads


@dataclass
class _Cell:
    id: str
    parent: str
    style: dict[str, str]
    label: str
    vertex: bool
    edge: bool
    geo: ET.Element | None
    source: str = ""
    target: str = ""
    order: int = 0
    children: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- detection


def looks_like_drawio(data: bytes, filename: str = "", content_type: str = "") -> bool:
    name = filename.lower()
    if name.endswith((".drawio", ".dio")):
        return True
    if not (
        name.endswith((".html", ".htm", ".xml")) or "html" in content_type or "xml" in content_type
    ):
        return False
    head = data[:200_000]
    return b"mxGraphModel" in head or b"data-mxgraph" in head or b"<mxfile" in head


# --------------------------------------------------------------------------- parsing


def _xml_documents(data: bytes) -> list[str]:
    text = data.decode("utf-8", errors="replace")
    if "data-mxgraph" in text:
        docs = []
        for raw in re.findall(r'data-mxgraph="([^"]*)"', text):
            try:
                docs.append(json.loads(html.unescape(raw))["xml"])
            except (json.JSONDecodeError, KeyError) as exc:
                raise DrawioError("Unreadable draw.io HTML export") from exc
        return docs
    return [text]


def _inflate(payload: str) -> str:
    try:
        raw = zlib.decompress(base64.b64decode(payload), -15)
    except (binascii.Error, zlib.error) as exc:
        raise DrawioError("Unreadable compressed draw.io page") from exc
    return urllib.parse.unquote(raw.decode("utf-8"))


def _pages(doc: str) -> list[tuple[str, ET.Element]]:
    try:
        root = ET.fromstring(doc.strip())
    except ET.ParseError as exc:
        raise DrawioError("Not a draw.io diagram") from exc
    if root.tag == "mxGraphModel":
        return [("Page-1", root)]
    if root.tag != "mxfile":
        raise DrawioError("Not a draw.io diagram")
    pages = []
    for i, diagram in enumerate(root.findall("diagram"), start=1):
        name = diagram.get("name") or f"Page-{i}"
        model = diagram.find("mxGraphModel")
        if model is None and (diagram.text or "").strip():
            model = ET.fromstring(_inflate(diagram.text.strip()))
        if model is not None:
            pages.append((name, model))
    return pages


def _style(style: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        key, sep, value = part.partition("=")
        out[key] = value if sep else "1"
    return out


def _label_text(value: str | None, is_html: bool) -> str:
    if not value:
        return ""
    if not is_html:
        return value.strip()
    text = re.sub(r"(?i)<br\s*/?>|</?(div|p|li|h\d)\b[^>]*>", "\n", value)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _cells(model: ET.Element) -> dict[str, _Cell]:
    root = model.find("root")
    if root is None:
        return {}
    cells: dict[str, _Cell] = {}
    for order, node in enumerate(root):
        # <UserObject>/<object> wrap an mxCell and carry the label themselves.
        cell = node if node.tag == "mxCell" else node.find("mxCell")
        if cell is None:
            continue
        cid = node.get("id") or cell.get("id") or f"_{order}"
        style = _style(cell.get("style"))
        value = node.get("label") if node.tag != "mxCell" else cell.get("value")
        cells[cid] = _Cell(
            id=cid,
            parent=cell.get("parent") or "",
            style=style,
            label=_label_text(value, style.get("html") == "1"),
            vertex=cell.get("vertex") == "1",
            edge=cell.get("edge") == "1",
            geo=cell.find("mxGeometry"),
            source=cell.get("source") or "",
            target=cell.get("target") or "",
            order=order,
        )
    for c in cells.values():
        if c.parent in cells:
            cells[c.parent].children.append(c.id)
    return cells


def _num(node: ET.Element | None, attr: str, default: float = 0) -> float:
    if node is None:
        return default
    try:
        return float(node.get(attr, default))
    except ValueError:
        return default


# --------------------------------------------------------------------------- mapping


class _Page:
    def __init__(self, cells: dict[str, _Cell]):
        self.cells = cells
        self.elements: list = []
        self.boxes: dict[str, tuple[float, float, float, float]] = {}
        self.round: set[str] = set()  # ellipse-like shapes (for where wires touch them)
        self.turned: set[str] = set()  # rotated shapes: lines end at their outline, unbound
        self.rendered: set[str] = set()
        self.images: list[str] = []

    # absolute position of a cell's origin (sum of vertex ancestors' x/y)
    def offset(self, cell_id: str) -> tuple[float, float]:
        x = y = 0.0
        cell = self.cells.get(cell_id)
        while cell is not None and cell.vertex and cell.geo is not None:
            x += _num(cell.geo, "x")
            y += _num(cell.geo, "y")
            cell = self.cells.get(cell.parent)
        return x, y

    def box(self, cell: _Cell) -> tuple[float, float, float, float]:
        px, py = self.offset(cell.parent)
        return (
            px + _num(cell.geo, "x"),
            py + _num(cell.geo, "y"),
            _num(cell.geo, "width"),
            _num(cell.geo, "height"),
        )

    def run(self) -> Scene:
        for cell in sorted(self.cells.values(), key=lambda c: c.order):
            if cell.vertex and cell.geo is not None:
                self.vertex(cell)
        for cell in sorted(self.cells.values(), key=lambda c: c.order):
            if cell.edge:
                self.edge(cell)
        return Scene(source="drawio", elements=self.elements)

    # ----------------------------------------------------------------- vertices

    def vertex(self, cell: _Cell) -> None:
        st = cell.style
        if st.get("group") == "1" or "edgeLabel" in st:
            return
        if self.cells.get(cell.parent) and self.cells[cell.parent].edge:
            return  # labels of connectors are handled with the connector
        x, y, w, h = self.box(cell)
        self.boxes[cell.id] = (x, y, w, h)
        rotation = float(st.get("rotation", 0) or 0)
        scale = round(float(st.get("fontSize", DEFAULT_FONT_PX)) / TLDRAW_S_FONT_PX, 3)
        shape = st.get("shape", "")

        if shape.startswith("stencil("):
            self.freehand(cell, st, x, y, w, h)
            return
        if shape == "image" or "image" in st:
            self.image(cell, st, x, y, w, h)
            return
        boxed_text = "text" in st and (
            st.get("fillColor") not in (None, "none")
            or st.get("strokeColor") not in (None, "none", "default")
        )
        if not boxed_text and (
            "text" in st
            or (st.get("strokeColor") == "none" and st.get("fillColor") in (None, "none"))
        ):
            if cell.label:
                align = _align(st.get("align", "center"))
                pad = float(st.get("spacing", 2) or 0)
                left = pad + float(st.get("spacingLeft", 0) or 0) if align == "start" else 0
                right = pad + float(st.get("spacingRight", 0) or 0) if align == "end" else 0
                self.add(
                    cell,
                    TextElement(
                        kind="text",
                        id=cell.id,
                        x=x + left,
                        y=y,
                        w=max(w - left - right, 10),
                        h=h,
                        text=cell.label,
                        size="s",
                        color=to_palette(st.get("fontColor")),
                        font="sans",
                        align=align,
                        wrap=st.get("whiteSpace") == "wrap",
                        scale=scale,
                        rotation=rotation,
                    ),
                )
            return

        geo, extra_rotation = _geo_kind(st)
        if geo in ("ellipse", "diamond"):
            self.round.add(cell.id)
        if extra_rotation or rotation:
            self.turned.add(cell.id)
        if boxed_text:
            pad = float(st.get("spacing", 2) or 0) + float(st.get("spacingLeft", 0) or 0)
            st = {**st, "align": st.get("align", "left") if pad else st.get("align", "center")}
        box = (x, y, w, h)
        if extra_rotation % 180 == 90:
            # A shape turned by a quarter fills the original box only with width and height
            # swapped (rotation is around the center).
            cx, cy = x + w / 2, y + h / 2
            w, h = h, w
            x, y = cx - w / 2, cy - h / 2
        is_lane = "swimlane" in st
        header = float(st.get("startSize", 26) or 26) if is_lane else 0
        stroke = st.get("strokeColor")
        fill_value = st.get("swimlaneFillColor", "none") if is_lane else st.get("fillColor")
        label = "" if extra_rotation or is_lane else cell.label
        if label:
            # Keep shapes their size: tldraw would grow a shape whose label does not fit.
            scale = min(scale, fit_wrapped_label_scale(w, h, label, scale))
        color = (
            to_palette(stroke)
            if stroke not in (None, "none", "default")
            else to_palette(st.get("fillColor"), "black")
        )
        if color == "white":
            color = "grey"
        self.add(
            cell,
            GeoElement(
                kind="geo",
                id=cell.id,
                x=x,
                y=y,
                w=max(w, 1),
                h=max(h, 1),
                geo=geo,
                color=color,
                fill=fill_style(fill_value, default_white=not is_lane),
                dash="dashed" if st.get("dashed") == "1" else "solid",
                # draw.io turns only the outline of e.g. a triangle, never its label;
                # a table's title goes on its header below.
                label=label,
                label_color=to_palette(st.get("fontColor")) if st.get("fontColor") else None,
                font="sans",
                size="s",
                align=_align(st.get("align", "center")),
                valign="start" if is_lane else _valign(st.get("verticalAlign", "middle")),
                scale=scale,
                rotation=rotation + extra_rotation,
                # draw.io's west-facing trapezoid is upside down (wide at the top).
                flip_y=geo == "trapezoid" and st.get("direction") in ("west", "south"),
            ),
        )
        if extra_rotation and cell.label:
            bx, by, bw, bh = box
            self.elements.append(
                TextElement(
                    kind="text",
                    id=f"{cell.id}~label",
                    x=bx,
                    y=by,
                    w=bw,
                    h=bh,
                    text=cell.label,
                    size="s",
                    font="sans",
                    align="middle",
                    scale=scale,
                    color=to_palette(st.get("fontColor")),
                    opacity=_opacity(st),
                )
            )
        if is_lane and st.get("horizontal") != "0":
            # The table's header: its own fill (draw.io's fillColor) and title.
            head_scale = (
                min(scale, fit_wrapped_label_scale(w, header, cell.label, scale))
                if cell.label
                else scale
            )
            self.elements.append(
                GeoElement(
                    kind="geo",
                    id=f"{cell.id}~header",
                    x=x,
                    y=y,
                    w=max(w, 1),
                    h=max(header, 1),
                    color=color,
                    fill=fill_style(st.get("fillColor"), default_white=True),
                    label=cell.label,
                    label_color=to_palette(st.get("fontColor")) if st.get("fontColor") else None,
                    font="sans",
                    size="s",
                    scale=head_scale,
                    opacity=_opacity(st),
                )
            )

    def add(self, cell: _Cell, element) -> None:
        element.opacity = _opacity(cell.style)
        self.elements.append(element)
        self.rendered.add(cell.id)

    def image(self, cell: _Cell, st: dict, x: float, y: float, w: float, h: float) -> None:
        src = st.get("image", "")
        m = re.match(r"data:image/([\w+.-]+)[^,]*,(.*)", src, re.S)
        if m:
            from app.imaging import store_embedded_image

            try:
                payload = base64.b64decode(urllib.parse.unquote(m.group(2)))
            except binascii.Error:
                payload = b""
            if 0 < len(payload) <= MAX_IMAGE_BYTES:
                stored = store_embedded_image(payload, m.group(1))
                if stored:
                    self.images.append(stored)
                    self.add(
                        cell,
                        ImageElement(
                            kind="image",
                            id=cell.id,
                            x=x,
                            y=y,
                            w=w,
                            h=h,
                            file=stored,
                            alt=cell.label,
                        ),
                    )
                    return
        # External or unreadable image: keep its place on the board. Never fetched.
        self.add(
            cell,
            GeoElement(
                kind="geo",
                id=cell.id,
                x=x,
                y=y,
                w=max(w, 1),
                h=max(h, 1),
                color="grey",
                dash="dashed",
                label=cell.label or "image",
                font="sans",
                size="s",
            ),
        )

    def freehand(self, cell: _Cell, st: dict, x: float, y: float, w: float, h: float) -> None:
        strokes = _stencil_strokes(st["shape"][len("stencil(") : -1])
        width = float(st.get("strokeWidth", 1) or 1)
        size = "s" if width <= 2 else "m" if width <= 4 else "l"
        for i, (w0, h0, points, filled) in enumerate(strokes):
            if len(points) < 2:
                continue
            abs_points = [Point(x=x + px / w0 * w, y=y + py / h0 * h) for px, py in points]
            self.elements.append(
                DrawElement(
                    kind="draw",
                    id=cell.id if i == 0 else f"{cell.id}~{i}",
                    points=abs_points,
                    # Newer draw.io stores ink as the filled outline of the stroke.
                    color=to_palette(st.get("fillColor") if filled else st.get("strokeColor")),
                    freehand=True,
                    closed=filled,
                    filled=filled,
                    size="s" if filled else size,
                    opacity=_opacity(st),
                )
            )
        self.rendered.add(cell.id)

    # ----------------------------------------------------------------- edges

    def touch_point(self, cid: str, toward: Point) -> Point:
        """Where a line from `toward` meets the outline of shape `cid` (aimed at its center)."""
        bx, by, bw, bh = self.boxes[cid]
        cx, cy = bx + bw / 2, by + bh / 2
        dx, dy = toward.x - cx, toward.y - cy
        if dx == 0 and dy == 0:
            return Point(x=cx, y=cy)
        hw, hh = max(bw / 2, 0.01), max(bh / 2, 0.01)
        if cid in self.round:
            t = 1 / math.sqrt((dx / hw) ** 2 + (dy / hh) ** 2)
        else:
            t = min(hw / abs(dx) if dx else math.inf, hh / abs(dy) if dy else math.inf)
        return Point(x=cx + dx * t, y=cy + dy * t)

    def polyline(self, cell, st, src, tgt, start, start_anchor, end, end_anchor, waypoints):
        """An edge routed through waypoints (e.g. circuit wires): straight segments, with an
        arrow on the last leg when the edge has an arrowhead."""
        if src and start_anchor is None:
            start = self.touch_point(src, waypoints[0])
        if tgt and end_anchor is None:
            end = self.touch_point(tgt, waypoints[-1])
        points = [start, *waypoints, end]
        if st.get("edgeStyle") in ("orthogonalEdgeStyle", "elbowEdgeStyle"):
            squared = [points[0]]
            for p in points[1:]:
                q = squared[-1]
                if q.x != p.x and q.y != p.y:
                    squared.append(Point(x=p.x, y=q.y))
                squared.append(p)
            points = squared
        color = to_palette(st.get("strokeColor"))
        end_head = _arrowhead(st.get("endArrow", "classic"))
        line_points = points if end_head == "none" else points[:-1]
        if len(line_points) >= 2:
            self.elements.append(
                DrawElement(
                    kind="draw",
                    id=f"{cell.id}~path",
                    points=line_points,
                    color=color,
                    smooth=False,
                    opacity=_opacity(st),
                )
            )
        if end_head != "none":
            a, b = points[-2], points[-1]
            self.elements.append(
                ConnectorElement(
                    kind="connector",
                    id=cell.id,
                    x1=a.x,
                    y1=a.y,
                    x2=b.x,
                    y2=b.y,
                    to_id=tgt,
                    to_anchor=end_anchor,
                    end_head=end_head,
                    color=color,
                    opacity=_opacity(st),
                )
            )

    def edge(self, cell: _Cell) -> None:
        st = cell.style
        geo = cell.geo
        px, py = self.offset(cell.parent)
        src = cell.source if cell.source in self.rendered and cell.source in self.boxes else ""
        tgt = cell.target if cell.target in self.rendered and cell.target in self.boxes else ""

        def terminal(cid: str, which: str, ax: str, ay: str) -> tuple[Point, Anchor | None]:
            if cid:
                bx, by, bw, bh = self.boxes[cid]
                if ax in st and ay in st:
                    anchor = Anchor(x=float(st[ax]), y=float(st[ay]))
                    return Point(x=bx + anchor.x * bw, y=by + anchor.y * bh), anchor
                return Point(x=bx + bw / 2, y=by + bh / 2), None
            node = geo.find(f"mxPoint[@as='{which}']") if geo is not None else None
            return Point(x=px + _num(node, "x"), y=py + _num(node, "y")), None

        start, start_anchor = terminal(src, "sourcePoint", "exitX", "exitY")
        end, end_anchor = terminal(tgt, "targetPoint", "entryX", "entryY")
        if not src and not tgt and start == end:
            return  # degenerate edge with no geometry
        # tldraw attaches arrows to rotated shapes poorly; end such lines at the outline.
        if tgt in self.turned:
            end, end_anchor, tgt = self.touch_point(tgt, start), None, ""
        if src in self.turned:
            start, start_anchor, src = self.touch_point(src, end), None, ""
        array = geo.find("Array[@as='points']") if geo is not None else None
        waypoints = [
            Point(x=px + _num(p, "x"), y=py + _num(p, "y"))
            for p in (array if array is not None else [])
        ]
        if waypoints:
            self.polyline(cell, st, src, tgt, start, start_anchor, end, end_anchor, waypoints)
            return

        labels = [cell.label] + [
            self.cells[c].label
            for c in cell.children
            if self.cells[c].vertex and self.cells[c].label
        ]
        if st.get("edgeStyle") in (
            "orthogonalEdgeStyle",
            "elbowEdgeStyle",
            "entityRelationEdgeStyle",
        ):
            route = "elbow"
            if src and tgt and _aligned(self.boxes[src], self.boxes[tgt]):
                # No bend needed; a straight arrow avoids tldraw re-routing it oddly.
                route = "straight"
        elif st.get("curved") == "1":
            route = "curved"
        else:
            route = "straight"
        self.elements.append(
            ConnectorElement(
                kind="connector",
                id=cell.id,
                x1=start.x,
                y1=start.y,
                x2=end.x,
                y2=end.y,
                from_id=src,
                to_id=tgt,
                from_anchor=start_anchor,
                to_anchor=end_anchor,
                route=route,
                start_head=_arrowhead(st.get("startArrow", "none")),
                end_head=_arrowhead(st.get("endArrow", "classic")),
                color=to_palette(st.get("strokeColor")),
                dash="dashed" if st.get("dashed") == "1" else "solid",
                label="\n".join(t for t in labels if t),
                scale=round(float(st.get("fontSize", DEFAULT_FONT_PX)) / TLDRAW_S_FONT_PX, 3),
                opacity=_opacity(st),
            )
        )


def _aligned(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """Shapes stacked in a column or sitting in a row (centers within 2 px)."""
    ax, ay = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx, by = b[0] + b[2] / 2, b[1] + b[3] / 2
    return abs(ax - bx) <= 2 or abs(ay - by) <= 2


def _opacity(st: dict[str, str]) -> float:
    try:
        return max(0.05, min(1.0, float(st.get("opacity", 100)) / 100))
    except ValueError:
        return 1.0


def _align(value: str) -> str:
    return {"left": "start", "right": "end"}.get(value, "middle")


def _valign(value: str) -> str:
    return {"top": "start", "bottom": "end"}.get(value, "middle")


def _arrowhead(value: str) -> Arrowhead:
    if value in ("none", "", "0"):
        return "none"
    if value in ("oval", "dash"):
        return "dot"
    if value in ("diamond", "diamondThin", "ERmandOne", "ERone"):
        return "diamond"
    if value in ("block", "blockThin"):
        return "triangle"
    return "arrow"


_SHAPE_TO_GEO: dict[str, GeoKind] = {
    "ellipse": "ellipse",
    "doubleEllipse": "ellipse",
    "rhombus": "diamond",
    "triangle": "triangle",
    "trapezoid": "trapezoid",
    "parallelogram": "rhombus",
    "hexagon": "hexagon",
    "cloud": "cloud",
    "star": "star",
    "singleArrow": "arrow-right",
}
# draw.io triangles point right by default; tldraw's point up.
_TRIANGLE_ROTATION = {"east": 90, "south": 180, "west": 270, "north": 0}


def _geo_kind(st: dict[str, str]) -> tuple[GeoKind, float]:
    for key in (st.get("shape", ""), *st.keys()):
        if key in _SHAPE_TO_GEO:
            geo = _SHAPE_TO_GEO[key]
            if geo == "triangle":
                return geo, _TRIANGLE_ROTATION.get(st.get("direction", "east"), 90)
            return geo, 0
    return "rectangle", 0


def _stencil_strokes(
    encoded: str,
) -> list[tuple[float, float, list[tuple[float, float]], bool]]:
    """Decode a draw.io stencil (how freehand pen strokes are stored) into polylines.

    The flag says whether the path is filled (an ink outline) rather than stroked."""
    try:
        shape = ET.fromstring(_inflate(encoded))
    except (DrawioError, ET.ParseError):
        return []
    w0 = float(shape.get("w", 100) or 100)
    h0 = float(shape.get("h", 100) or 100)
    filled = any(node.tag in ("fill", "fillstroke") for node in shape.iter())
    strokes: list[tuple[float, float, list[tuple[float, float]], bool]] = []
    for path in shape.iter("path"):
        current: list[tuple[float, float]] = []
        for cmd in path:
            if cmd.tag == "move":
                if len(current) > 1:
                    strokes.append((w0, h0, current, filled))
                current = [(float(cmd.get("x", 0)), float(cmd.get("y", 0)))]
            elif cmd.tag == "line":
                current.append((float(cmd.get("x", 0)), float(cmd.get("y", 0))))
            elif cmd.tag in ("quad", "curve") and current:
                ctrl = [
                    (float(cmd.get(f"x{i}", 0)), float(cmd.get(f"y{i}", 0)))
                    for i in (1, 2, 3)
                    if cmd.get(f"x{i}") is not None
                ]
                start = current[-1]
                for t in (0.25, 0.5, 0.75, 1.0):
                    current.append(_bezier([start, *ctrl], t))
            elif cmd.tag == "close" and current:
                current.append(current[0])
        if len(current) > 1:
            strokes.append((w0, h0, current, filled))
    return strokes


def _bezier(pts: list[tuple[float, float]], t: float) -> tuple[float, float]:
    while len(pts) > 1:
        pts = [
            (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            for a, b in zip(pts, pts[1:], strict=False)
        ]
    return pts[0]


# --------------------------------------------------------------------------- entry point


def import_drawio(data: bytes) -> list[ImportedPage]:
    """All non-empty pages of a draw.io document. Embedded images are written to uploads.

    On failure, images already written are removed and a DrawioError is raised.
    """
    written: list[str] = []
    try:
        return _import(data, written)
    except Exception as exc:
        from app.imaging import remove_images

        remove_images(written)
        if isinstance(exc, DrawioError):
            raise
        raise DrawioError("Could not read this draw.io file") from exc


def _import(data: bytes, written: list[str]) -> list[ImportedPage]:
    pages: list[ImportedPage] = []
    for doc in _xml_documents(data):
        for name, model in _pages(doc):
            page = _Page(_cells(model))
            try:
                scene = page.run()
            finally:
                written += page.images
            if not scene.elements:
                continue
            min_x, min_y, max_x, max_y = scene.bounds()
            scene = scene.translated(MARGIN - min_x, MARGIN - min_y)
            scene.title = _title(name, scene)
            scene.transcript = board_reading(scene)
            pages.append(
                ImportedPage(
                    name=name,
                    scene=scene,
                    width=math.ceil(max_x - min_x + 2 * MARGIN),
                    height=math.ceil(max_y - min_y + 2 * MARGIN),
                    files=page.images,
                )
            )
    if not pages:
        raise DrawioError("The draw.io file has no shapes")
    return pages


def _title(page_name: str, scene: Scene) -> str:
    if not re.fullmatch(r"Page-\d+", page_name):
        return page_name
    labels = sorted(
        (el.y, el.x, (getattr(el, "text", "") or getattr(el, "label", "")).splitlines()[0])
        for el in scene.elements
        if (getattr(el, "text", "") or getattr(el, "label", "")).strip()
    )
    for _, _, text in labels:
        if sum(ch.isalpha() for ch in text) >= 3:
            return text[:80]
    return "draw.io board"
