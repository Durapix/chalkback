import html
import json
from pathlib import Path

import pytest

from app.ai.vision import VisionScene
from app.config import get_settings
from app.importers.drawio import DrawioError, import_drawio, looks_like_drawio
from app.scene import ConnectorElement, DrawElement, GeoElement, ImageElement, TextElement

FIXTURE = Path(__file__).parents[1] / "app" / "demo" / "linked_list.drawio"


def by_id(scene, element_id):
    return next(el for el in scene.elements if el.id == element_id)


@pytest.fixture
def pages():
    return import_drawio(FIXTURE.read_bytes())


def test_imports_every_page_including_compressed(pages):
    assert [p.name for p in pages] == ["Linked list", "Flowchart"]
    flow = pages[1].scene
    assert {el.label for el in flow.elements if isinstance(el, GeoElement)} == {
        "Почетак",
        "Улаз: n",
        "Крај",
    }


def test_connectors_stay_attached_to_their_shapes(pages):
    scene = pages[0].scene
    nxt = by_id(scene, "e0")
    assert isinstance(nxt, ConnectorElement)
    # An angled (orthogonal) draw.io edge between shapes in one row needs no bend.
    assert (nxt.from_id, nxt.to_id, nxt.route) == ("p0", "d1", "straight")
    head = by_id(scene, "eh")
    assert head.label == "first node"
    loose = by_id(scene, "loose")
    assert (loose.from_id, loose.to_id, loose.dash) == ("", "", "dashed")
    assert by_id(scene, "eg").route == "curved"


def test_nested_shapes_get_absolute_positions(pages):
    scene = pages[0].scene
    lane, row = by_id(scene, "lane"), by_id(scene, "r2")
    assert isinstance(row, TextElement)
    assert row.y == lane.y + 56
    assert row.text == "name\nemail"
    # The group container itself is not drawn; its children are, offset by the group.
    assert not any(el.id == "grp" for el in scene.elements)
    assert by_id(scene, "start").x == by_id(scene, "lane").x + 280


def test_styles_pen_strokes_and_images(pages):
    scene = pages[0].scene
    node = by_id(scene, "d0")
    assert (node.color, node.fill, node.label) == ("blue", "solid", "7")
    ink = by_id(scene, "ink")
    assert isinstance(ink, DrawElement) and ink.freehand and ink.color == "green"
    assert len(ink.points) == 3
    pic = by_id(scene, "pic")
    assert isinstance(pic, ImageElement)
    assert (get_settings().uploads_dir / pic.file).exists()
    assert pages[0].files == [pic.file]
    tri = by_id(scene, "tri")  # draw.io triangles point right: rotated, box swapped
    assert (tri.rotation, tri.w, tri.h) == (90, 60, 40)
    # Tables get a header with draw.io's header fill and the title; the body has no label.
    header, lane = by_id(scene, "lane~header"), by_id(scene, "lane")
    assert (header.y, header.h, header.label, header.fill) == (lane.y, 26, "Student", "solid")
    assert lane.label == ""


def test_transcript_reads_labels_and_connections(pages):
    transcript = pages[0].scene.transcript
    assert "head" in transcript
    assert "next -> 3" in transcript
    assert "head -> 7 (first node)" in transcript


def test_html_export_wrapper_is_understood():
    xml = FIXTURE.read_text(encoding="utf-8")
    attr = html.escape(json.dumps({"highlight": "#0000ff", "xml": xml}), quote=True)
    page = f'<html><body><div class="mxgraph" data-mxgraph="{attr}"></div></body></html>'
    data = page.encode()
    assert looks_like_drawio(data, "board.html", "text/html")
    assert [p.name for p in import_drawio(data)] == ["Linked list", "Flowchart"]


def test_rejects_non_diagrams():
    assert not looks_like_drawio(b"<html>hello</html>", "x.html", "text/html")
    with pytest.raises(DrawioError):
        import_drawio(b"<mxfile><diagram>not base64!</diagram></mxfile>")


def test_svg_images_become_placeholders():
    svg = "data:image/svg+xml,PHN2Zy8+"
    doc = (
        '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'<mxCell id="i" style="shape=image;image={svg};" vertex="1" parent="1">'
        '<mxGeometry width="40" height="40" as="geometry"/></mxCell></root></mxGraphModel>'
    )
    (page,) = import_drawio(doc.encode())
    (el,) = page.scene.elements
    assert isinstance(el, GeoElement) and el.dash == "dashed"
    assert page.files == []


def test_vision_scene_conversion():
    vision = VisionScene.model_validate(
        {
            "title": "Arrays",
            "transcript": "",
            "elements": [
                {"kind": "note", "id": "n", "x": 0, "y": 0, "side": 10, "text": "x",
                 "color": "orange"},
                {"kind": "grid", "id": "g", "x": 100, "y": 50, "rows": 2, "cols": 2, "side": 10,
                 "gap_x": 5, "gap_y": 1,
                 "cells": [{"text": str(i), "color": "yellow"} for i in range(4)]},
                {"kind": "region", "id": "r", "x": 1, "y": 2, "w": 3, "h": 4,
                 "description": "task"},
                {"kind": "frame", "id": "f", "x": 0, "y": 0, "w": 50, "h": 50, "title": "A"},
                {"kind": "connector", "id": "c", "from_id": "n", "to_id": "g:1:1", "x1": 0,
                 "y1": 0, "x2": 1, "y2": 1, "route": "curved", "arrowheads": "none",
                 "color": "violet", "label": ""},
            ],
        }
    )  # fmt: skip
    scene = vision.to_scene(2.0)
    kinds = [el.kind for el in scene.elements]
    assert kinds[:2] == ["frame", "image"]  # backgrounds first
    cell = by_id(scene, "g:1:1")
    assert (cell.x, cell.y, cell.w, cell.text) == ((100 + 15) * 2, (50 + 11) * 2, 20, "3")
    region = by_id(scene, "r")
    assert region.crop.model_dump() == {"x": 2, "y": 4, "w": 6, "h": 8}
    conn = by_id(scene, "c")
    assert (conn.to_id, conn.end_head, conn.route) == ("g:1:1", "none", "curved")


def _model(cells: str) -> bytes:
    return (
        '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        + cells
        + "</root></mxGraphModel>"
    ).encode()


def test_colored_table_cells_keep_their_fill_and_labels_fit():
    (page,) = import_drawio(
        _model(
            '<mxCell id="t" value="Students" style="swimlane;startSize=30;fillColor=#f8cecc;"'
            ' vertex="1" parent="1"><mxGeometry width="140" height="90" as="geometry"/></mxCell>'
            '<mxCell id="r" value="Item 2" style="text;fillColor=#d5e8d4;strokeColor=#82b366;'
            'spacingLeft=4;" vertex="1" parent="t">'
            '<mxGeometry y="30" width="140" height="30" as="geometry"/></mxCell>'
            '<mxCell id="b" value="Shift all digits to the left" style="whiteSpace=wrap;"'
            ' vertex="1" parent="1"><mxGeometry y="200" width="120" height="40"'
            ' as="geometry"/></mxCell>'
        )
    )
    scene = page.scene
    row = by_id(scene, "r")
    assert isinstance(row, GeoElement)
    assert (row.color, row.fill, row.label, row.align) == (
        "green",
        "solid",
        "Item 2",
        "start",
    )
    header = by_id(scene, "t~header")
    assert (header.color, header.fill, header.label) == ("light-red", "solid", "Students")
    assert "Item 2 (green)" in scene.transcript
    box = by_id(scene, "b")  # two lines must fit 40 px, so the label is scaled down
    assert box.scale < 12 / 18


def test_waypoint_wires_are_polylines_and_flipped_trapezoids():
    (page,) = import_drawio(
        _model(
            '<mxCell id="a" value="R1" style="" vertex="1" parent="1">'
            '<mxGeometry x="100" y="0" width="100" height="40" as="geometry"/></mxCell>'
            '<mxCell id="c" value="R2" style="" vertex="1" parent="1">'
            '<mxGeometry x="100" y="100" width="100" height="40" as="geometry"/></mxCell>'
            '<mxCell id="w" style="endArrow=none;" edge="1" parent="1" source="a" target="c">'
            '<mxGeometry relative="1" as="geometry"><Array as="points">'
            '<mxPoint x="40" y="70"/></Array></mxGeometry></mxCell>'
            '<mxCell id="f" value="FROM" style="shape=trapezoid;direction=west;" vertex="1"'
            ' parent="1"><mxGeometry x="300" width="120" height="40" as="geometry"/></mxCell>'
        )
    )
    scene = page.scene
    wire = by_id(scene, "w~path")
    assert isinstance(wire, DrawElement) and not wire.smooth
    # R1's outline -> waypoint -> R2's outline
    assert len(wire.points) == 3 and wire.points[1].x == by_id(scene, "a").x - 60
    assert by_id(scene, "f").flip_y
